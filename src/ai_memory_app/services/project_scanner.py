from __future__ import annotations

import fnmatch
from pathlib import Path

from .agent_catalog import load_agent_catalog


def _matches(relative_path: str, pattern: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    if "/" not in pattern:
        return Path(normalized).name == pattern
    return fnmatch.fnmatch(normalized, pattern)


def classify_markdown(relative_path: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    parent = Path(relative_path).parent.as_posix()
    scope = "專案根目錄" if parent == "." else f"目錄：{parent}"
    for agent in load_agent_catalog()["agents"]:
        for file_type in agent["files"]:
            if any(_matches(relative_path, pattern) for pattern in file_type["patterns"]):
                load_status = "可能載入"
                if agent["id"] == "openclaw" and parent != ".":
                    load_status = "非預設載入位置"
                elif file_type["id"] == "claude_rule":
                    load_status = "依規則設定載入"
                matches.append(
                    {
                        "agent_id": agent["id"],
                        "agent_name": agent["name"],
                        "file_type_id": file_type["id"],
                        "file_label": file_type["label"],
                        "purpose": file_type["purpose"],
                        "scope": scope,
                        "load_status": load_status,
                    }
                )
    return matches


def scan_project(project_path: Path) -> dict:
    files: list[dict] = []
    detected_agents: set[str] = set()
    project_root = project_path.resolve(strict=True)
    for path in sorted(project_path.rglob("*.md"), key=lambda item: str(item).lower()):
        try:
            actual = path.resolve(strict=True)
        except OSError:
            continue
        if not actual.is_file() or not actual.is_relative_to(project_root):
            continue
        relative_path = path.relative_to(project_path).as_posix()
        classifications = classify_markdown(relative_path)
        detected_agents.update(item["agent_id"] for item in classifications)
        files.append(
            {
                "name": path.name,
                "relative_path": relative_path,
                "size": path.stat().st_size,
                "recognized": bool(classifications),
                "classifications": classifications,
            }
        )
    return {
        "name": project_path.name,
        "path": str(project_path),
        "files": files,
        "detected_agents": sorted(detected_agents),
        "recognized_count": sum(1 for item in files if item["recognized"]),
        "markdown_count": len(files),
    }
