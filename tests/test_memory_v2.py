from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.agent_catalog import load_agent_catalog
from ai_memory_app.services.desktop_api import DesktopApi
from ai_memory_app.services.memory_compiler import compile_memory_module


class AgentCatalogTests(unittest.TestCase):
    def test_catalog_contains_four_supported_agents_and_sources(self) -> None:
        catalog = load_agent_catalog()
        self.assertEqual({agent["id"] for agent in catalog["agents"]}, {"codex", "claude", "gemini", "openclaw"})
        self.assertTrue(all(agent["sources"] for agent in catalog["agents"]))
        self.assertTrue(all(module["fields"] for module in catalog["modules"]))


class CompilerTests(unittest.TestCase):
    def test_every_supported_file_type_has_deterministic_compilable_output(self) -> None:
        catalog = load_agent_catalog()
        modules = {module["id"]: module for module in catalog["modules"]}
        compiled_file_types = set()

        for agent in catalog["agents"]:
            for file_type in agent["files"]:
                module = modules[file_type["modules"][0]]
                values = {}
                for field in module["fields"]:
                    if field.get("required"):
                        values[field["id"]] = (
                            "第一項\n第二項" if field["type"] == "list" else "pytest -q" if field["type"] == "code" else "固定測試內容"
                        )
                request = {
                    "original": "# 手寫內容\n\n請保留。\n",
                    "filename": file_type["path"],
                    "agent_id": agent["id"],
                    "file_type_id": file_type["id"],
                    "module_id": module["id"],
                    "values": values,
                }
                first = compile_memory_module(**request)
                second = compile_memory_module(**request)
                self.assertEqual(first.compiled, second.compiled)
                self.assertIn("請保留。", first.compiled)
                self.assertIn(f"AI Memory Manager:start {module['id']}", first.compiled)
                compiled_file_types.add((agent["id"], file_type["id"]))

        expected = {
            (agent["id"], file_type["id"])
            for agent in catalog["agents"]
            for file_type in agent["files"]
        }
        self.assertEqual(compiled_file_types, expected)

    def test_compiler_preserves_manual_text_and_updates_only_managed_module(self) -> None:
        original = "# Manual\n\nDo not remove this.\n"
        first = compile_memory_module(
            original=original,
            filename="AGENTS.md",
            agent_id="codex",
            file_type_id="codex_agents",
            module_id="project_overview",
            values={"purpose": "管理 AI 記憶", "goals": "離線使用\n清楚預覽"},
        )
        self.assertIn("Do not remove this.", first.compiled)
        self.assertIn("- 離線使用", first.compiled)
        second = compile_memory_module(
            original=first.compiled,
            filename="AGENTS.md",
            agent_id="codex",
            file_type_id="codex_agents",
            module_id="project_overview",
            values={"purpose": "新版用途", "goals": "安全寫回"},
        )
        self.assertEqual(second.compiled.count("AI Memory Manager:start project_overview"), 1)
        self.assertNotIn("離線使用", second.compiled)
        self.assertIn("新版用途", second.compiled)

    def test_compiler_reports_required_fields_and_formats_code(self) -> None:
        result = compile_memory_module(
            original="",
            filename="AGENTS.md",
            agent_id="codex",
            file_type_id="codex_agents",
            module_id="commands",
            values={"setup": "python -m venv .venv", "test": ""},
        )
        self.assertIn("```bash", result.compiled)
        self.assertTrue(any(item.startswith("必填") for item in result.warnings))


class DesktopApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "projects"
        self.project = self.root / "demo"
        self.project.mkdir(parents=True)
        self.db_path = self.base / "app.sqlite3"
        initialize_database(self.db_path)
        self.repository = MemoryRepository(self.db_path)
        self.api = DesktopApi(self.repository, backup_root=self.base / "backups")
        self.assertTrue(self.api.set_project_root(str(self.root))["ok"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _request(self, **overrides) -> dict:
        request = {
            "project_path": str(self.project),
            "relative_path": "AGENTS.md",
            "agent_id": "codex",
            "file_type_id": "codex_agents",
            "module_id": "project_overview",
            "values": {"purpose": "測試專案", "goals": "安全寫回"},
        }
        request.update(overrides)
        return request

    def test_database_migration_preserves_v1_data_and_adds_v2_schema(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            count = connection.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
        self.assertIn("root_path", columns)
        self.assertIn("last_scanned_at", columns)
        self.assertIn("memory_file_changes", tables)
        self.assertGreater(count, 0)

    def test_apply_detects_external_change_and_restore_returns_exact_content(self) -> None:
        target = self.project / "AGENTS.md"
        original = "# Existing\n\nKeep me.\n"
        target.write_text(original, encoding="utf-8")
        preview = self.api.compile_memory_module(self._request())
        self.assertTrue(preview["ok"])
        request = self._request(base_hash=preview["data"]["base_hash"])
        applied = self.api.apply_memory_change(request)
        self.assertTrue(applied["ok"], applied["error"])
        self.assertIn("Keep me.", target.read_text(encoding="utf-8"))

        stale_preview = self.api.compile_memory_module(self._request())
        target.write_text(target.read_text(encoding="utf-8") + "\nExternal edit.\n", encoding="utf-8")
        rejected = self.api.apply_memory_change(self._request(base_hash=stale_preview["data"]["base_hash"]))
        self.assertFalse(rejected["ok"])
        self.assertIn("其他程式修改", rejected["error"])

        target.write_text(applied_content := preview["data"]["compiled"], encoding="utf-8")
        change = self.repository.get_memory_file_change(applied["data"]["change_id"])
        self.assertEqual(change["output_hash"], __import__("hashlib").sha256(applied_content.encode()).hexdigest())
        restored = self.api.restore_change(applied["data"]["change_id"])
        self.assertTrue(restored["ok"], restored["error"])
        self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_new_file_can_be_restored_by_removing_it(self) -> None:
        preview = self.api.compile_memory_module(self._request())
        applied = self.api.apply_memory_change(self._request(base_hash=preview["data"]["base_hash"]))
        self.assertTrue(applied["ok"], applied["error"])
        self.assertTrue((self.project / "AGENTS.md").exists())
        restored = self.api.restore_change(applied["data"]["change_id"])
        self.assertTrue(restored["ok"], restored["error"])
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_path_traversal_and_external_symlink_are_rejected(self) -> None:
        traversal = self.api.read_memory_file(str(self.project), "../outside.md")
        self.assertFalse(traversal["ok"])
        outside = self.base / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        link = self.project / "linked.md"
        link.symlink_to(outside)
        linked = self.api.read_memory_file(str(self.project), "linked.md")
        self.assertFalse(linked["ok"])
        scan = self.api.scan_project(str(self.project))
        self.assertTrue(scan["ok"], scan["error"])
        self.assertNotIn("linked.md", {item["relative_path"] for item in scan["data"]["files"]})

    def test_health_check_finds_wrong_name_and_possible_secret(self) -> None:
        (self.project / "AGENT.md").write_text("password: hunter2\n", encoding="utf-8")
        result = self.api.run_memory_health_check(str(self.project), "codex")
        self.assertTrue(result["ok"], result["error"])
        codes = {issue["code"] for issue in result["data"]["issues"]}
        self.assertIn("wrong_filename", codes)
        self.assertIn("possible_secret", codes)


if __name__ == "__main__":
    unittest.main()
