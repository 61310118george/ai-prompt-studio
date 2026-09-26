from __future__ import annotations

from pathlib import Path

from .database import connect, utc_now
from .models import MemoryItem, MemoryVersion


class MemoryRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def list_memory_items(self, main_area: str | None = None) -> list[MemoryItem]:
        query = "SELECT * FROM memory_items"
        params: tuple[object, ...] = ()
        if main_area:
            query += " WHERE main_area = ?"
            params = (main_area,)
        query += " ORDER BY updated_at DESC, id DESC"

        with connect(self.db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_memory_item(row) for row in rows]

    def create_memory_item(
        self,
        *,
        main_area: str,
        category: str,
        title: str,
        content: str,
        tags: str = "",
        importance: int = 3,
        enabled: bool = True,
        source: str = "manual",
        project_id: int | None = 1,
    ) -> int:
        now = utc_now()
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO memory_items
                  (project_id, main_area, category, title, content, status, importance, enabled, tags, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'confirmed', ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    main_area,
                    category,
                    title,
                    content,
                    importance,
                    1 if enabled else 0,
                    tags,
                    source,
                    now,
                    now,
                ),
            )
            memory_item_id = int(cursor.lastrowid)
            self._insert_version(connection, memory_item_id, 1, title, content, "建立記憶", source)
        return memory_item_id

    def update_memory_item(
        self,
        memory_item_id: int,
        *,
        category: str,
        title: str,
        content: str,
        tags: str,
        importance: int,
        enabled: bool,
        change_summary: str = "更新記憶",
    ) -> None:
        now = utc_now()
        with connect(self.db_path) as connection:
            current = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) AS version FROM memory_versions WHERE memory_item_id = ?",
                (memory_item_id,),
            ).fetchone()
            next_version = int(current["version"]) + 1
            connection.execute(
                """
                UPDATE memory_items
                SET category = ?, title = ?, content = ?, tags = ?, importance = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (category, title, content, tags, importance, 1 if enabled else 0, now, memory_item_id),
            )
            self._insert_version(
                connection,
                memory_item_id,
                next_version,
                title,
                content,
                change_summary,
                "user",
            )

    def list_tool_templates(self) -> list[dict[str, str]]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT tool_key, display_name, description, template_content FROM tool_templates WHERE enabled = 1 ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_tool_template(self, tool_key: str) -> dict[str, str] | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT tool_key, display_name, description, template_content
                FROM tool_templates
                WHERE tool_key = ? AND enabled = 1
                """,
                (tool_key,),
            ).fetchone()
        return dict(row) if row else None

    def list_versions(self, memory_item_id: int) -> list[MemoryVersion]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM memory_versions
                WHERE memory_item_id = ?
                ORDER BY version_number DESC
                """,
                (memory_item_id,),
            ).fetchall()
        return [
            MemoryVersion(
                id=int(row["id"]),
                memory_item_id=int(row["memory_item_id"]),
                version_number=int(row["version_number"]),
                title=row["title"],
                content=row["content"],
                change_summary=row["change_summary"],
                changed_by=row["changed_by"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def delete_memory_item(self, memory_item_id: int) -> None:
        with connect(self.db_path) as connection:
            connection.execute("DELETE FROM memory_versions WHERE memory_item_id = ?", (memory_item_id,))
            connection.execute("DELETE FROM memory_items WHERE id = ?", (memory_item_id,))

    def record_ai_processing_run(
        self,
        *,
        input_text: str,
        processing_goal: str,
        target_category: str | None,
        output_format: str,
        used_api: bool,
        output_text: str,
        status: str = "completed",
        error_message: str | None = None,
    ) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO ai_processing_runs
                  (input_text, processing_goal, target_category, output_format, used_api, output_text, status, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    input_text,
                    processing_goal,
                    target_category,
                    output_format,
                    1 if used_api else 0,
                    output_text,
                    status,
                    error_message,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def record_export(
        self,
        *,
        export_type: str,
        output_format: str,
        file_path: str,
        item_count: int,
    ) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO exports (export_type, output_format, file_path, item_count, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (export_type, output_format, file_path, item_count, utc_now()),
            )
            return int(cursor.lastrowid)

    def remember_project_root(self, root_path: str, name: str | None = None) -> int:
        with connect(self.db_path) as connection:
            existing = connection.execute(
                "SELECT id FROM projects WHERE root_path = ?", (root_path,)
            ).fetchone()
            now = utc_now()
            if existing:
                project_id = int(existing["id"])
                connection.execute(
                    "UPDATE projects SET name = COALESCE(?, name), last_scanned_at = ?, updated_at = ? WHERE id = ?",
                    (name, now, now, project_id),
                )
                return project_id
            cursor = connection.execute(
                """
                INSERT INTO projects (name, description, status, root_path, last_scanned_at, created_at, updated_at)
                VALUES (?, ?, 'active', ?, ?, ?, ?)
                """,
                (name or Path(root_path).name, "由 AI Memory Manager 2.0 加入的本機專案。", root_path, now, now, now),
            )
            return int(cursor.lastrowid)

    def record_memory_file_change(
        self,
        *,
        project_path: str,
        relative_path: str,
        agent_id: str,
        file_type_id: str,
        module_id: str,
        base_hash: str,
        output_hash: str,
        diff_text: str,
        backup_path: str | None,
        original_existed: bool,
    ) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO memory_file_changes
                  (project_path, relative_path, agent_id, file_type_id, module_id,
                   base_hash, output_hash, diff_text, backup_path, original_existed, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'applied', ?)
                """,
                (
                    project_path, relative_path, agent_id, file_type_id, module_id,
                    base_hash, output_hash, diff_text, backup_path, int(original_existed), utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_memory_file_changes(self, project_path: str) -> list[dict]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM memory_file_changes
                WHERE project_path = ? ORDER BY created_at DESC, id DESC LIMIT 100
                """,
                (project_path,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_memory_file_change(self, change_id: int) -> dict | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM memory_file_changes WHERE id = ?", (change_id,)
            ).fetchone()
        return dict(row) if row else None

    def mark_memory_file_change_restored(self, change_id: int) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                "UPDATE memory_file_changes SET status = 'restored', restored_at = ? WHERE id = ?",
                (utc_now(), change_id),
            )

    def _insert_version(
        self,
        connection,
        memory_item_id: int,
        version_number: int,
        title: str,
        content: str,
        change_summary: str,
        changed_by: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO memory_versions
              (memory_item_id, version_number, title, content, change_summary, changed_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_item_id, version_number, title, content, change_summary, changed_by, utc_now()),
        )

    def _row_to_memory_item(self, row) -> MemoryItem:
        return MemoryItem(
            id=int(row["id"]),
            project_id=row["project_id"],
            main_area=row["main_area"],
            category=row["category"],
            title=row["title"],
            content=row["content"],
            status=row["status"],
            importance=int(row["importance"]),
            enabled=bool(row["enabled"]),
            tags=row["tags"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
