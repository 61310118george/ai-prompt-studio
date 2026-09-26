from __future__ import annotations

import difflib
import hashlib
import html
import re
from dataclasses import asdict, dataclass

from .agent_catalog import get_file_type, get_module


MANAGED_START = "<!-- AI Memory Manager:start {module_id} -->"
MANAGED_END = "<!-- AI Memory Manager:end {module_id} -->"


@dataclass(frozen=True)
class CompileResult:
    original: str
    rendered_module: str
    compiled: str
    diff: str
    warnings: list[str]
    base_hash: str
    agent_id: str
    file_type_id: str
    module_id: str

    def to_dict(self) -> dict:
        return asdict(self)


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _clean_text(value: object) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return html.escape(text, quote=False)


def _list_items(value: object) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value or "").splitlines()
    items: list[str] = []
    for raw in raw_items:
        item = re.sub(r"^\s*(?:[-*+] |\d+[.)]\s*)", "", str(raw)).strip()
        if item:
            items.append(html.escape(item, quote=False))
    return items


def render_module(module_id: str, values: dict) -> tuple[str, list[str]]:
    module = get_module(module_id)
    warnings: list[str] = []
    sections: list[str] = [f"## {module['title']}"]
    for field in module["fields"]:
        value = values.get(field["id"], "")
        is_empty = not value or (isinstance(value, list) and not any(str(item).strip() for item in value))
        if is_empty:
            if field.get("required"):
                warnings.append(f"必填欄位尚未填寫：{field['label']}")
            continue
        field_type = field["type"]
        if field_type == "list":
            items = _list_items(value)
            if not items:
                continue
            body = "\n".join(f"- {item}" for item in items)
        elif field_type == "code":
            cleaned = _clean_text(value)
            if not cleaned:
                continue
            body = f"```bash\n{cleaned}\n```"
        else:
            body = _clean_text(value)
            if not body:
                continue
        sections.append(f"### {field['label']}\n\n{body}")
    start = MANAGED_START.format(module_id=module_id)
    end = MANAGED_END.format(module_id=module_id)
    return f"{start}\n{'\n\n'.join(sections)}\n{end}", warnings


def merge_managed_module(original: str, module_id: str, rendered: str) -> str:
    start = re.escape(MANAGED_START.format(module_id=module_id))
    end = re.escape(MANAGED_END.format(module_id=module_id))
    pattern = re.compile(rf"{start}.*?{end}", re.DOTALL)
    normalized_original = original.replace("\r\n", "\n").replace("\r", "\n")
    if pattern.search(normalized_original):
        merged = pattern.sub(lambda _match: rendered, normalized_original, count=1)
    elif normalized_original.strip():
        merged = normalized_original.rstrip() + "\n\n" + rendered
    else:
        merged = rendered
    return merged.rstrip() + "\n"


def compile_memory_module(
    *, original: str, filename: str, agent_id: str, file_type_id: str, module_id: str, values: dict
) -> CompileResult:
    file_type = get_file_type(agent_id, file_type_id)
    if module_id not in file_type["modules"]:
        raise ValueError(f"模組 {module_id} 不適用於 {file_type['label']}")
    rendered, warnings = render_module(module_id, values)
    compiled = merge_managed_module(original, module_id, rendered)
    diff = "\n".join(
        difflib.unified_diff(
            original.splitlines(), compiled.splitlines(),
            fromfile=f"{filename}（目前）", tofile=f"{filename}（預覽）", lineterm=""
        )
    )
    if compiled == original:
        warnings.append("產生內容與目前檔案相同。")
    return CompileResult(
        original=original,
        rendered_module=rendered,
        compiled=compiled,
        diff=diff,
        warnings=warnings,
        base_hash=content_hash(original),
        agent_id=agent_id,
        file_type_id=file_type_id,
        module_id=module_id,
    )
