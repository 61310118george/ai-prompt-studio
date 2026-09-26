from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import difflib
from datetime import datetime, timezone
from pathlib import Path

from ai_memory_app.data.database import APP_SUPPORT_DIR
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.data.prompt_library import PromptLibrary

from .agent_catalog import get_file_type, load_agent_catalog
from .memory_compiler import compile_memory_module, content_hash
from .memory_health import run_memory_health_check
from .project_scanner import scan_project
from .prompt_workbench import analyze_prompt, validate_text


class DesktopApi:
    def __init__(self, repository: MemoryRepository, window=None, backup_root: Path | None = None) -> None:
        self.repository = repository
        self.window = window
        self.allowed_root: Path | None = None
        self.backup_root = backup_root or (APP_SUPPORT_DIR / "backups")
        self.prompts = PromptLibrary(repository.db_path)

    def attach_window(self, window) -> None:
        self.window = window

    def _response(self, data=None, *, error: str | None = None) -> dict:
        return {"ok": error is None, "data": data, "error": error}

    def _safe_call(self, callback):
        try:
            return self._response(callback())
        except (OSError, ValueError, KeyError) as exc:
            return self._response(error=str(exc))

    def _authorize_root(self, value: str) -> Path:
        root = Path(value).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("選擇的根目錄不存在。")
        self.allowed_root = root
        return root

    def _project_path(self, value: str) -> Path:
        if self.allowed_root is None:
            raise ValueError("請先選擇專案根目錄。")
        project = Path(value).expanduser().resolve(strict=True)
        if not project.is_dir() or not project.is_relative_to(self.allowed_root):
            raise ValueError("專案不在已授權的根目錄內。")
        return project

    def _target_path(self, project: Path, relative_path: str, *, must_exist: bool = False) -> Path:
        if not relative_path or Path(relative_path).is_absolute() or Path(relative_path).suffix.lower() != ".md":
            raise ValueError("只能操作專案內的相對 Markdown 路徑。")
        target = project / relative_path
        if ".." in Path(relative_path).parts or target.is_symlink():
            raise ValueError("不允許 .. 或 symlink 作為寫入目標。")
        resolved_parent = target.parent.resolve(strict=True) if target.parent.exists() else self._resolve_future_parent(project, target.parent)
        resolved = resolved_parent / target.name
        if not resolved.is_relative_to(project.resolve()):
            raise ValueError("檔案路徑超出專案範圍。")
        if target.exists():
            actual = target.resolve(strict=True)
            if not actual.is_relative_to(project.resolve()):
                raise ValueError("不允許透過 symlink 操作專案外檔案。")
            if not actual.is_file():
                raise ValueError("目標不是檔案。")
            return actual
        if must_exist:
            raise ValueError("找不到指定的 Markdown 檔案。")
        return resolved

    @staticmethod
    def _resolve_future_parent(project: Path, parent: Path) -> Path:
        missing: list[str] = []
        current = parent
        while not current.exists():
            missing.append(current.name)
            current = current.parent
        resolved = current.resolve(strict=True)
        for name in reversed(missing):
            resolved = resolved / name
        if not resolved.is_relative_to(project.resolve()):
            raise ValueError("新檔案路徑超出專案範圍。")
        return resolved

    def choose_project_root(self) -> dict:
        def choose():
            if self.window is None:
                raise ValueError("瀏覽器預覽模式請使用示範資料，或在桌面 App 選擇資料夾。")
            import webview
            selected = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            if not selected:
                return None
            raw = selected[0] if isinstance(selected, (list, tuple)) else selected
            return str(self._authorize_root(str(raw)))
        return self._safe_call(choose)

    def set_project_root(self, root: str) -> dict:
        return self._safe_call(lambda: str(self._authorize_root(root)))

    def list_projects(self, root: str) -> dict:
        def load():
            root_path = self._authorize_root(root)
            projects = [{"name": f"{root_path.name}（根目錄）", "path": str(root_path)}]
            for path in sorted((item for item in root_path.iterdir() if item.is_dir() and not item.name.startswith(".")), key=lambda item: item.name.lower()):
                if path.resolve().is_relative_to(root_path):
                    projects.append({"name": path.name, "path": str(path)})
            return projects
        return self._safe_call(load)

    def scan_project(self, project_path: str) -> dict:
        def load():
            project = self._project_path(project_path)
            self.repository.remember_project_root(str(project), project.name)
            return scan_project(project)
        return self._safe_call(load)

    def read_memory_file(self, project_path: str, relative_path: str) -> dict:
        def load():
            project = self._project_path(project_path)
            target = self._target_path(project, relative_path)
            exists = target.exists()
            content = target.read_text(encoding="utf-8") if exists else ""
            return {"relative_path": relative_path, "exists": exists, "content": content, "hash": content_hash(content)}
        return self._safe_call(load)

    def get_agent_catalog(self) -> dict:
        return self._response(load_agent_catalog())

    def list_prompts(self, project_path: str, query: str = "", category: str = "", archived: bool = False) -> dict:
        return self._safe_call(lambda: self.prompts.list(str(self._project_path(project_path)), query, category, archived))

    def save_prompt(self, request: dict) -> dict:
        return self._safe_call(lambda: self.prompts.save(str(self._project_path(request["project_path"])), request))

    def list_prompt_versions(self, project_path: str, prompt_id: int) -> dict:
        return self._safe_call(lambda: self.prompts.history(str(self._project_path(project_path)), prompt_id))

    def analyze_prompt(self, request: dict) -> dict:
        return self._safe_call(lambda: analyze_prompt(request))

    def preview_prompt_file(self, request: dict) -> dict:
        def preview():
            project = self._project_path(request["project_path"])
            target = self._target_path(project, request["relative_path"])
            original = target.read_bytes().decode("utf-8") if target.exists() else ""
            content = validate_text(request.get("content", ""))
            return {"original": original, "compiled": content, "exists": target.exists(),
                    "base_hash": content_hash(original), "relative_path": request["relative_path"],
                    "diff": "\n".join(difflib.unified_diff(original.splitlines(), content.splitlines(), fromfile="目前檔案", tofile="提示詞匯出", lineterm=""))}
        return self._safe_call(preview)

    def apply_prompt_file(self, request: dict) -> dict:
        def apply():
            project = self._project_path(request["project_path"])
            target = self._target_path(project, request["relative_path"])
            preview = self.preview_prompt_file(request)
            if not preview["ok"]:
                raise ValueError(preview["error"])
            result = preview["data"]
            if result["base_hash"] != request.get("base_hash") or result["exists"] != request.get("expected_exists"):
                raise ValueError("檔案已變更，請重新產生匯出預覽。")
            if not result["compiled"].strip():
                raise ValueError("不允許匯出空白提示詞。")
            if result["exists"] and not request.get("confirm_replace", False):
                raise ValueError("此操作會替換整個 Markdown 檔案，請先確認 Diff。")
            backup = None
            if result["exists"]:
                backup = self._backup_path(project, request["relative_path"])
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            self._atomic_write(target, result["compiled"])
            change_id = self.repository.record_memory_file_change(
                project_path=str(project), relative_path=request["relative_path"], agent_id="generic", file_type_id="prompt",
                module_id="prompt_export", base_hash=result["base_hash"], output_hash=content_hash(result["compiled"]),
                diff_text=result["diff"], backup_path=str(backup) if backup else None, original_existed=result["exists"])
            return {"change_id": change_id, "relative_path": request["relative_path"]}
        return self._safe_call(apply)

    def compile_memory_module(self, request: dict) -> dict:
        def compile_request():
            project = self._project_path(request["project_path"])
            relative_path = request.get("relative_path") or get_file_type(request["agent_id"], request["file_type_id"])["path"]
            target = self._target_path(project, relative_path)
            original = target.read_text(encoding="utf-8") if target.exists() else ""
            result = compile_memory_module(
                original=original,
                filename=relative_path,
                agent_id=request["agent_id"],
                file_type_id=request["file_type_id"],
                module_id=request["module_id"],
                values=request.get("values", {}),
            )
            payload = result.to_dict()
            payload["relative_path"] = relative_path
            return payload
        return self._safe_call(compile_request)

    def _backup_path(self, project: Path, relative_path: str) -> Path:
        project_key = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:16]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        return self.backup_root / project_key / stamp / relative_path

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def apply_memory_change(self, request: dict) -> dict:
        def apply():
            project = self._project_path(request["project_path"])
            relative_path = request.get("relative_path") or get_file_type(request["agent_id"], request["file_type_id"])["path"]
            target = self._target_path(project, relative_path)
            existed = target.exists()
            original = target.read_text(encoding="utf-8") if existed else ""
            if content_hash(original) != request["base_hash"]:
                raise ValueError("檔案已在預覽後被其他程式修改，請重新產生預覽。")
            result = compile_memory_module(
                original=original,
                filename=relative_path,
                agent_id=request["agent_id"],
                file_type_id=request["file_type_id"],
                module_id=request["module_id"],
                values=request.get("values", {}),
            )
            if result.warnings and any(message.startswith("必填") for message in result.warnings):
                raise ValueError("仍有必填欄位未填寫，不能套用。")
            backup: Path | None = None
            if existed:
                backup = self._backup_path(project, relative_path)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            self._atomic_write(target, result.compiled)
            output_hash = content_hash(result.compiled)
            change_id = self.repository.record_memory_file_change(
                project_path=str(project), relative_path=relative_path,
                agent_id=request["agent_id"], file_type_id=request["file_type_id"], module_id=request["module_id"],
                base_hash=result.base_hash, output_hash=output_hash, diff_text=result.diff,
                backup_path=str(backup) if backup else None, original_existed=existed,
            )
            return {"change_id": change_id, "relative_path": relative_path, "output_hash": output_hash, "backup_path": str(backup) if backup else None}
        return self._safe_call(apply)

    def list_change_history(self, project_path: str) -> dict:
        return self._safe_call(lambda: self.repository.list_memory_file_changes(str(self._project_path(project_path))))

    def restore_change(self, change_id: int) -> dict:
        def restore():
            change = self.repository.get_memory_file_change(int(change_id))
            if not change:
                raise ValueError("找不到指定變更紀錄。")
            project = self._project_path(change["project_path"])
            target = self._target_path(project, change["relative_path"], must_exist=True)
            current = target.read_bytes().decode("utf-8")
            if content_hash(current) != change["output_hash"]:
                raise ValueError("檔案在套用後又有其他修改，為避免覆蓋新內容，無法直接復原。")
            if change["original_existed"]:
                backup = Path(change["backup_path"]).resolve(strict=True)
                backup_root = self.backup_root.resolve(strict=True)
                if not backup.is_relative_to(backup_root) or not backup.is_file():
                    raise ValueError("備份檔案不存在或位置不安全。")
                self._atomic_write(target, backup.read_bytes().decode("utf-8"))
            else:
                target.unlink()
            self.repository.mark_memory_file_change_restored(int(change_id))
            return {"change_id": int(change_id), "relative_path": change["relative_path"], "restored": True}
        return self._safe_call(restore)

    def run_memory_health_check(self, project_path: str, agent_id: str) -> dict:
        return self._safe_call(lambda: run_memory_health_check(self._project_path(project_path), agent_id))
