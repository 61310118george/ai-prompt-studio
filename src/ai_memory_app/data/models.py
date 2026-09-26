from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryItem:
    id: int
    project_id: int | None
    main_area: str
    category: str
    title: str
    content: str
    status: str
    importance: int
    enabled: bool
    tags: str | None
    source: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MemoryVersion:
    id: int
    memory_item_id: int
    version_number: int
    title: str
    content: str
    change_summary: str | None
    changed_by: str
    created_at: str
