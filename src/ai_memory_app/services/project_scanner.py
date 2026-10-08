from __future__ import annotations

import fnmatch
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_catalog import load_agent_catalog


OUTPUT_PATH_PATTERN = re.compile(r'(?:^|/)(?:deliverables?|outputs?)(?:/|$)|(?:企劃書|交付驗收|符合度|展示指南|第三方來源)', re.I)


def classify_group(relative_path: str, classifications: list[dict[str, str]]) -> str:
    parts = Path(relative_path).parts
    if Path(relative_path).name.lower() == 'skill.md' or 'skills' in parts:
        return 'skills'
    if classifications:
        return 'core'
    if OUTPUT_PATH_PATTERN.search(relative_path.replace('\\', '/')):
        return 'outputs'
    return 'prompts'


def markdown_title(path: Path) -> str:
    """Read only a bounded prefix; avoid interpreting code/YAML as a heading."""
    try:
        with path.open('rb') as stream:
            text = stream.read(8192).decode('utf-8-sig', errors='replace')
    except OSError:
        return ''
    fence = None
    frontmatter = False
    for index, line in enumerate(text.splitlines()):
        if index == 0 and line.strip() == '---':
            frontmatter = True
            continue
        if frontmatter:
            if line.strip() in {'---', '...'}:
                frontmatter = False
            continue
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            value = marker.group(1)
            if fence is None:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = None
            continue
        if fence is None:
            heading = re.match(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
            if heading:
                return heading.group(1)[:120]
    return ''


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
    warnings = []
    candidates = []
    for directory, dirs, names in os.walk(project_path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'build', 'dist', '.pytest_cache'} and not (Path(directory) / d).is_symlink())
        candidates.extend(Path(directory) / name for name in sorted(names) if name.lower().endswith('.md'))
        if len(candidates) > 5000:
            warnings.append('檔案超過 5,000 個，本次只掃描前 5,000 個 Markdown。')
            candidates = candidates[:5000]
            break
    for path in candidates:
        try:
            actual = path.resolve(strict=True)
        except (OSError, RuntimeError):
            warnings.append(f'無法讀取：{path.name}')
            continue
        if path.is_symlink() or not actual.is_file() or not actual.is_relative_to(project_root):
            continue
        relative_path = path.relative_to(project_path).as_posix()
        classifications = classify_markdown(relative_path)
        detected_agents.update(item["agent_id"] for item in classifications)
        files.append(
            {
                "name": path.name,
                "title": markdown_title(actual),
                "relative_path": relative_path,
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "group": classify_group(relative_path, classifications),
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
        "warnings": warnings,
    }
