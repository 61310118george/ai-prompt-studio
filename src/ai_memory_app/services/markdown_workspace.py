from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarkdownProject:
    name: str
    path: Path


@dataclass(frozen=True)
class MarkdownFile:
    name: str
    path: Path
    relative_path: str


def list_projects(root: Path) -> list[MarkdownProject]:
    if not root.exists() or not root.is_dir():
        return []
    projects = [MarkdownProject(path.name, path) for path in root.iterdir() if path.is_dir()]
    return sorted(projects, key=lambda item: item.name.lower())


def list_markdown_files(project_path: Path) -> list[MarkdownFile]:
    if not project_path.exists() or not project_path.is_dir():
        return []
    files: list[MarkdownFile] = []
    for path in project_path.rglob("*.md"):
        if path.is_file():
            files.append(
                MarkdownFile(
                    name=path.name,
                    path=path,
                    relative_path=str(path.relative_to(project_path)),
                )
            )
    return sorted(files, key=lambda item: item.relative_path.lower())


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_markdown(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_unified_diff(original: str, revised: str, *, filename: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            revised.splitlines(),
            fromfile=f"{filename}（原始）",
            tofile=f"{filename}（修改後）",
            lineterm="",
        )
    )


def offline_revise_markdown(original: str, instruction: str) -> str:
    instruction = instruction.strip()
    if not instruction:
        return original
    note = (
        "\n\n---\n"
        "## 待套用修改指令\n\n"
        f"{instruction}\n\n"
        "> 目前未使用 AI API，因此系統先將修改指令附加到檔案底部。"
        "填入 API Key 後可由 AI 直接改寫全文。\n"
    )
    return original.rstrip() + note

