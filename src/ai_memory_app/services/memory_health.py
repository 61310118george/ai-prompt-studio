from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .agent_catalog import get_agent
from .project_scanner import classify_markdown, scan_project


SECRET_PATTERNS = [
    ("OpenAI API Key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("私密金鑰", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("密碼欄位", re.compile(r"(?i)(?:password|passwd|密碼)\s*[:=]\s*\S+")),
]


def _issue(level: str, code: str, title: str, detail: str, path: str = "") -> dict:
    return {"level": level, "code": code, "title": title, "detail": detail, "path": path}


def _effective_files(project: Path, agent_id: str, working_directory: Path | None = None) -> list[dict]:
    working = (working_directory or project).resolve()
    paths: list[dict] = []
    agent = get_agent(agent_id)
    candidates: list[Path] = []
    if agent_id in {"codex", "claude", "gemini"}:
        current = project.resolve()
        target = working if working.is_relative_to(current) else current
        while True:
            candidates.append(current)
            if current == target:
                break
            relative_parts = target.relative_to(current).parts
            if not relative_parts:
                break
            current = current / relative_parts[0]
    else:
        candidates = [project.resolve()]

    for directory in candidates:
        for file_type in agent["files"]:
            candidate = directory / file_type["path"]
            if candidate.exists() and candidate.is_file() and candidate.resolve().is_relative_to(project.resolve()):
                paths.append(
                    {
                        "relative_path": candidate.relative_to(project).as_posix(),
                        "purpose": file_type["purpose"],
                        "scope": "working-directory" if directory == working else "project",
                    }
                )
    if agent_id == "claude":
        rules_dir = project / ".claude" / "rules"
        if rules_dir.exists():
            for rule in sorted(rules_dir.glob("*.md")):
                paths.append({"relative_path": rule.relative_to(project).as_posix(), "purpose": "Claude 模組化規則", "scope": "rule"})
    return paths


def run_memory_health_check(project_path: Path, agent_id: str, working_directory: Path | None = None) -> dict:
    scan = scan_project(project_path)
    agent = get_agent(agent_id)
    issues: list[dict] = []
    all_rules: dict[str, list[str]] = defaultdict(list)
    total_chars = 0

    found_paths = {item["relative_path"] for item in scan["files"]}
    for file_type in agent["files"]:
        recommended = file_type["path"]
        if "*" not in recommended and recommended not in found_paths:
            level = "warning" if file_type == agent["files"][0] else "info"
            issues.append(_issue(level, "missing_file", f"缺少 {file_type['label']}", file_type["purpose"], recommended))

    if "AGENT.md" in found_paths:
        issues.append(_issue("error", "wrong_filename", "可能使用了錯誤檔名 AGENT.md", "多數支援共同規格的 Agent 使用 AGENTS.md（含 S）。", "AGENT.md"))

    for file_info in scan["files"]:
        path = project_path / file_info["relative_path"]
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(_issue("error", "encoding", "Markdown 不是 UTF-8", "請先轉換成 UTF-8 再由 App 管理。", file_info["relative_path"]))
            continue
        total_chars += len(content)
        if len(content) > 24_000:
            issues.append(_issue("warning", "large_file", "記憶檔案偏長", f"目前 {len(content):,} 字元；這是 App 的保守提醒值，建議拆分非必要細節。", file_info["relative_path"]))
        if not content.strip():
            issues.append(_issue("info", "empty_file", "記憶檔案是空白的", "可從記憶編程選擇模組建立內容。", file_info["relative_path"]))
        for secret_name, pattern in SECRET_PATTERNS:
            if pattern.search(content):
                issues.append(_issue("error", "possible_secret", f"偵測到可能的{secret_name}", "記憶檔會進入模型上下文，請移除或改用安全的憑證儲存。", file_info["relative_path"]))
        if classify_markdown(file_info["relative_path"]):
            for line in content.splitlines():
                normalized = re.sub(r"^\s*[-*+]\s*", "", line).strip().lower()
                if len(normalized) >= 12:
                    all_rules[normalized].append(file_info["relative_path"])

    for rule, paths in all_rules.items():
        unique_paths = sorted(set(paths))
        if len(unique_paths) > 1:
            issues.append(_issue("info", "duplicate_rule", "多個檔案包含相同規則", f"「{rule[:80]}」出現在：{', '.join(unique_paths)}"))

    effective = _effective_files(project_path, agent_id, working_directory)
    return {
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "issues": issues,
        "summary": {
            "errors": sum(item["level"] == "error" for item in issues),
            "warnings": sum(item["level"] == "warning" for item in issues),
            "info": sum(item["level"] == "info" for item in issues),
            "characters": total_chars,
            "estimated_tokens": round(total_chars / 4),
        },
        "effective_files": effective,
        "load_behavior": agent["load_behavior"],
    }
