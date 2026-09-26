from __future__ import annotations

from ai_memory_app.data.models import MemoryItem


def build_memory_block(items: list[MemoryItem]) -> str:
    enabled_items = [item for item in items if item.enabled]
    if not enabled_items:
        return "目前沒有啟用的記憶。"
    lines: list[str] = []
    for item in enabled_items:
        lines.append(f"### {item.title}")
        lines.append(f"- 分類：{item.category}")
        if item.tags:
            lines.append(f"- 標籤：{item.tags}")
        lines.append(item.content)
        lines.append("")
    return "\n".join(lines).strip()


def build_rules_block(items: list[MemoryItem]) -> str:
    rules = [
        item
        for item in items
        if item.enabled and item.category in {"preferences_constraints", "ai_personality", "project_requirements"}
    ]
    if not rules:
        return "請依照使用者提供的上下文協助完成任務。"
    return "\n".join(f"- {item.content}" for item in rules)


def render_tool_prompt(tool_key: str, template_content: str, items: list[MemoryItem]) -> str:
    memory = build_memory_block(items)
    rules = build_rules_block(items)
    rendered = template_content.replace("{memory}", memory).replace("{rules}", rules)
    if tool_key == "codex":
        return rendered.strip() + "\n"
    if tool_key == "claude":
        return rendered.strip() + "\n"
    return rendered.strip()

