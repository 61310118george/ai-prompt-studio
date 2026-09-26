from pathlib import Path
import socket
import sqlite3

import pytest

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.desktop_api import DesktopApi
from ai_memory_app.services.prompt_workbench import _encoding, analyze_prompt, count_tokens


@pytest.fixture
def api(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    db = tmp_path / "test.sqlite3"
    initialize_database(db)
    instance = DesktopApi(MemoryRepository(db), backup_root=tmp_path / "backups")
    assert instance.set_project_root(str(root))["ok"]
    return instance, root, db


def test_tokenizers_are_available_without_network(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Unexpected network request")
    _encoding.cache_clear()
    monkeypatch.setattr(socket, "socket", no_network)
    for name in ("o200k_base", "cl100k_base"):
        assert count_tokens("hello world", name)["count"] == 2
        assert count_tokens("繁體中文 <|endoftext|>", name)["exact_text"]
        assert count_tokens("", name)["count"] == 0


def test_optimizer_preserves_code_constraints_and_placeholders():
    code = "```python\nprint('x')\n\n\nprint('x')\n```\n"
    text = "## 任務\n\n\n- 不可省略 {{customer}}。\n- 不可省略 {{customer}}。\n\n" + code
    default = analyze_prompt({"content": text})
    assert default["candidate"].count("不可省略") == 2
    result = analyze_prompt({"content": text, "remove_duplicates": True, "input_price": 2.5, "calls": 1000})
    assert code in result["candidate"]
    assert result["candidate"].count("不可省略 {{customer}}。") == 1
    assert result["saved_tokens"] > 0
    assert result["cost"]["saved"] == pytest.approx(result["saved_tokens"] * .0025)
    assert analyze_prompt({"content": "只需這一句。"})["saved_tokens"] == 0


@pytest.mark.parametrize("payload", [
    {"content": "x", "input_price": float("nan")},
    {"content": "x", "input_price": -1},
    {"content": "x", "calls": 0},
    {"content": "x", "calls": 1.5},
    {"content": "x", "encoding": "nonexistent"},
    {"content": "x" * 200001},
])
def test_analysis_rejects_invalid_inputs(payload):
    with pytest.raises(ValueError):
        analyze_prompt(payload)


def test_library_versions_scoping_search_and_archive(api, tmp_path):
    service, root, db = api
    request = {"project_path": str(root), "title": "客服回覆", "content": "請保留退款限制。", "category": "客服", "tags": "refund,繁中"}
    first = service.save_prompt(request)["data"]
    assert first["version"] == 1
    assert service.list_prompts(str(root), "REFUND")["data"][0]["id"] == first["id"]
    assert service.list_prompts(str(root), category="開發")["data"] == []
    second = service.save_prompt({**request, "id": first["id"], "version": 1, "content": "請先確認訂單。"})
    assert second["ok"]
    stale = service.save_prompt({**request, "id": first["id"], "version": 1})
    assert not stale["ok"]
    history = service.list_prompt_versions(str(root), first["id"])["data"]
    assert [x["version"] for x in history] == [2, 1]
    assert history[-1]["content"] == request["content"]
    archived = service.save_prompt({**second["data"], "archived": True})
    assert archived["ok"]
    assert service.list_prompts(str(root))["data"] == []
    assert len(service.list_prompts(str(root), archived=True)["data"]) == 1
    other = root / "other"
    other.mkdir()
    assert not service.save_prompt({**archived["data"], "project_path": str(other)})["ok"]
    assert service.list_prompt_versions(str(other), first["id"])["data"] == []
    initialize_database(db)
    assert len(service.list_prompt_versions(str(root), first["id"])["data"]) == 3


def test_export_diff_conflict_and_byte_exact_restore(api):
    service, root, _ = api
    target = root / "prompt.md"
    original = b"# handwritten\r\n\r\nKeep me.\r\n"
    target.write_bytes(original)
    request = {"project_path": str(root), "relative_path": "prompt.md", "content": "# 新提示词\n\n請幫忙測試。\n"}
    preview = service.preview_prompt_file(request)["data"]
    apply = {**request, "base_hash": preview["base_hash"], "expected_exists": True, "confirm_replace": True}
    assert not service.apply_prompt_file({**apply, "confirm_replace": False})["ok"]
    target.write_text("外部變更", encoding="utf-8")
    assert not service.apply_prompt_file(apply)["ok"]
    target.write_bytes(original)
    result = service.apply_prompt_file(apply)
    assert result["ok"], result
    assert service.restore_change(result["data"]["change_id"])["ok"]
    assert target.read_bytes() == original


def test_empty_project_and_file_existence_guard(api):
    service, root, _ = api
    assert service.list_projects(str(root))["data"][0]["path"] == str(root)
    request = {"project_path": str(root), "relative_path": "prompts/new.md", "content": "new"}
    preview = service.preview_prompt_file(request)["data"]
    target = root / "prompts" / "new.md"
    target.parent.mkdir()
    target.touch()
    assert not service.apply_prompt_file({**request, "base_hash": preview["base_hash"], "expected_exists": False})["ok"]


def test_new_schema_preserves_existing_settings(api):
    service, root, db_path = api
    with sqlite3.connect(db_path) as db:
        count = db.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
        db.execute("UPDATE settings SET value='claude' WHERE key='default_output_tool'")
    initialize_database(db_path)
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0] == count
        assert db.execute("SELECT value FROM settings WHERE key='default_output_tool'").fetchone()[0] == "claude"
        assert db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=3").fetchone()[0] == 1
