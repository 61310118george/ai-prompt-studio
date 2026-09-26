from __future__ import annotations

import csv
from pathlib import Path

from ai_memory_app.data.models import MemoryItem


def export_memory_csv(items: list[MemoryItem], file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "main_area",
                "category",
                "title",
                "content",
                "status",
                "importance",
                "enabled",
                "tags",
                "source",
                "created_at",
                "updated_at",
            ]
        )
        for item in items:
            writer.writerow(
                [
                    item.id,
                    item.main_area,
                    item.category,
                    item.title,
                    item.content,
                    item.status,
                    item.importance,
                    int(item.enabled),
                    item.tags or "",
                    item.source or "",
                    item.created_at,
                    item.updated_at,
                ]
            )


def export_prompt_markdown(content: str, file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

