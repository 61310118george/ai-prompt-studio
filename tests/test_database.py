from pathlib import Path

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.repository import MemoryRepository


def test_database_initializes_with_seed_data(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    initialize_database(db_path)

    repository = MemoryRepository(db_path)
    about_me = repository.list_memory_items("about_me")
    templates = repository.list_tool_templates()

    assert about_me
    assert {template["tool_key"] for template in templates} == {"codex", "chatgpt", "claude"}


def test_create_and_update_memory_item(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    initialize_database(db_path)

    repository = MemoryRepository(db_path)
    item_id = repository.create_memory_item(
        main_area="about_me",
        category="workflow_style",
        title="工作方式",
        content="偏好小步快跑。",
        tags="workflow",
    )
    repository.update_memory_item(
        item_id,
        category="workflow_style",
        title="工作方式",
        content="偏好小步快跑，並保留明確下一步。",
        tags="workflow,next-action",
        importance=4,
        enabled=True,
    )

    items = repository.list_memory_items("about_me")
    target = next(item for item in items if item.id == item_id)

    assert target.importance == 4
    assert "明確下一步" in target.content

