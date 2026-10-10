from pathlib import Path
import socket
import sqlite3

import pytest

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.desktop_api import DesktopApi, LOCAL_PROMPT_SCOPE
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


def test_prompt_title_is_limited_to_twenty_characters(api):
    service, root, _ = api
    accepted = service.save_prompt({"project_path": str(root), "title": "一" * 20, "content": "內容"})
    rejected = service.save_prompt({"project_path": str(root), "title": "一" * 21, "content": "內容"})
    assert accepted["ok"]
    assert not rejected["ok"] and "1–20" in rejected["error"]


def test_personal_prompt_library_works_without_selecting_a_project(tmp_path):
    db = tmp_path / "personal.sqlite3"
    initialize_database(db)
    service = DesktopApi(MemoryRepository(db), backup_root=tmp_path / "backups")
    saved = service.save_prompt({"project_path": LOCAL_PROMPT_SCOPE, "title": "個人範本", "content": "內容"})
    assert saved["ok"]
    assert service.create_prompt_group(LOCAL_PROMPT_SCOPE, "常用")["ok"]
    order = [f"prompt:{saved['data']['id']}", "template:develop-feature"]
    assert service.place_prompt_card(LOCAL_PROMPT_SCOPE, order[0], "常用", order)["ok"]
    assert [item["card_key"] for item in service.list_prompt_card_order(LOCAL_PROMPT_SCOPE)["data"]] == order
    assert service.set_prompt_template_preference(LOCAL_PROMPT_SCOPE, "develop-feature", "常用", True)["ok"]


def test_native_prompt_import_and_export_do_not_require_a_project(tmp_path):
    source = tmp_path / "本機範本.md"
    source.write_text("# 任務\n\n請保留限制。\n", encoding="utf-8")
    destination = tmp_path / "匯出結果"

    class DialogWindow:
        def __init__(self):
            self.responses = [(str(source),), (str(destination),)]
            self.calls = []

        def create_file_dialog(self, dialog_type, **options):
            self.calls.append((dialog_type, options))
            return self.responses.pop(0)

    window = DialogWindow()
    db = tmp_path / "native-files.sqlite3"
    initialize_database(db)
    service = DesktopApi(MemoryRepository(db), window=window, backup_root=tmp_path / "backups")

    imported = service.import_prompt_file()
    assert imported["ok"]
    assert imported["data"]["name"] == "本機範本"
    assert imported["data"]["content"] == source.read_text(encoding="utf-8")

    exported = service.export_prompt_file("客服/回覆", imported["data"]["content"])
    assert exported["ok"]
    assert exported["data"]["path"] == str(destination.with_suffix(".md"))
    assert destination.with_suffix(".md").read_text(encoding="utf-8") == imported["data"]["content"]
    assert window.calls[1][1]["save_filename"] == "客服-回覆.md"


def test_prompt_groups_can_be_created_and_used_for_drag_move(api):
    service, root, _ = api
    item = service.save_prompt({"project_path": str(root), "title": "可移動範本", "content": "內容", "category": "一般"})["data"]
    created = service.create_prompt_group(str(root), "課堂作業")["data"]
    assert created["name"] == "課堂作業"
    moved = service.move_prompt_to_group(str(root), item["id"], "課堂作業")["data"]
    assert moved["category"] == "課堂作業"
    assert [group["name"] for group in service.list_prompt_groups(str(root))["data"]][:2] == ["課堂作業", "一般"]


def test_prompt_and_group_delete_are_scoped_and_keep_group_items(api):
    service, root, _ = api
    first = service.save_prompt({"project_path": str(root), "title": "保留範本", "content": "內容", "category": "研究"})["data"]
    second = service.save_prompt({"project_path": str(root), "title": "刪除範本", "content": "內容", "category": "研究"})["data"]
    service.create_prompt_group(str(root), "研究")
    removed_group = service.delete_prompt_group(str(root), "研究")
    assert removed_group["ok"] and removed_group["data"]["moved_prompts"] == 2
    items = service.list_prompts(str(root))["data"]
    assert {item["category"] for item in items} == {"一般"}
    assert not service.delete_prompt_group(str(root), "一般")["ok"]
    deleted = service.delete_prompt(str(root), second["id"])
    assert deleted["ok"] and deleted["data"]["deleted"]
    assert [item["id"] for item in service.list_prompts(str(root))["data"]] == [first["id"]]
    assert service.list_prompt_versions(str(root), second["id"])["data"] == []


def test_builtin_template_preferences_can_move_hide_restore_and_follow_group_delete(api):
    service, root, _ = api
    service.create_prompt_group(str(root), "課堂範本")
    moved = service.set_prompt_template_preference(str(root), "develop-feature", "課堂範本", False)
    assert moved["ok"] and moved["data"]["category"] == "課堂範本"
    preferences = service.list_prompt_template_preferences(str(root))["data"]
    assert preferences == [moved["data"]]
    removed_group = service.delete_prompt_group(str(root), "課堂範本")["data"]
    assert removed_group["moved_templates"] == 1
    assert service.list_prompt_template_preferences(str(root))["data"][0]["category"] == "一般"
    hidden = service.set_prompt_template_preference(str(root), "develop-feature", "一般", True)["data"]
    assert hidden["hidden"] is True
    reset = service.reset_prompt_template_preferences(str(root))["data"]
    assert reset["removed"] == 1
    assert service.list_prompt_template_preferences(str(root))["data"] == []


def test_default_builtin_group_can_be_deleted_with_safe_fallback(api):
    service, root, _ = api
    removed = service.delete_prompt_group(str(root), "開發", ["develop-feature", "debug-direction"])
    assert removed["ok"] and removed["data"]["moved_templates"] == 2
    preferences = service.list_prompt_template_preferences(str(root))["data"]
    assert {item["template_key"] for item in preferences} == {"develop-feature", "debug-direction"}
    assert {item["category"] for item in preferences} == {"一般"}


def test_cards_can_be_reordered_within_the_same_group_and_persist(api):
    service, root, _ = api
    first = service.save_prompt({"project_path": str(root), "title": "第一張", "content": "內容", "category": "一般"})["data"]
    second = service.save_prompt({"project_path": str(root), "title": "第二張", "content": "內容", "category": "一般"})["data"]
    order = [f"prompt:{second['id']}", "template:develop-feature", f"prompt:{first['id']}"]
    placed = service.place_prompt_card(str(root), f"prompt:{second['id']}", "一般", order)
    assert placed["ok"] and placed["data"]["ordered_card_keys"] == order
    stored = service.list_prompt_card_order(str(root))["data"]
    assert [item["card_key"] for item in stored] == order
    assert {item["group_name"] for item in stored} == {"一般"}


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
        assert db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=5").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=6").fetchone()[0] == 1
