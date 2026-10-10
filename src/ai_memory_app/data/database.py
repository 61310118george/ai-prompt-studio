from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ai_memory_app.platform_paths import get_app_data_dir, get_default_db_path


APP_DIR = Path(__file__).resolve().parents[3]
APP_SUPPORT_DIR = get_app_data_dir()
DEFAULT_DB_PATH = get_default_db_path()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  value_type TEXT NOT NULL DEFAULT 'text',
  description TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER,
  main_area TEXT NOT NULL,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'confirmed',
  importance INTEGER NOT NULL DEFAULT 3,
  enabled INTEGER NOT NULL DEFAULT 1,
  tags TEXT,
  source TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS memory_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_item_id INTEGER NOT NULL,
  version_number INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  change_summary TEXT,
  changed_by TEXT NOT NULL DEFAULT 'user',
  created_at TEXT NOT NULL,
  FOREIGN KEY (memory_item_id) REFERENCES memory_items(id)
);

CREATE TABLE IF NOT EXISTS prompt_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  purpose TEXT,
  content TEXT NOT NULL,
  target_tool TEXT NOT NULL DEFAULT 'any',
  use_case TEXT,
  variables_json TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  tags TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tool_key TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT '1.0',
  description TEXT,
  template_content TEXT NOT NULL,
  source_note TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_processing_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  input_text TEXT NOT NULL,
  processing_goal TEXT NOT NULL,
  target_category TEXT,
  output_format TEXT NOT NULL,
  used_api INTEGER NOT NULL DEFAULT 0,
  model_name TEXT,
  output_text TEXT,
  token_input_estimate INTEGER,
  token_output_estimate INTEGER,
  status TEXT NOT NULL DEFAULT 'completed',
  error_message TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  export_type TEXT NOT NULL,
  output_format TEXT NOT NULL,
  file_path TEXT,
  item_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_file_changes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  file_type_id TEXT NOT NULL,
  module_id TEXT NOT NULL,
  base_hash TEXT NOT NULL,
  output_hash TEXT NOT NULL,
  diff_text TEXT NOT NULL,
  backup_path TEXT,
  original_existed INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'applied',
  created_at TEXT NOT NULL,
  restored_at TEXT
);

CREATE TABLE IF NOT EXISTS prompt_library (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_path TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT '一般',
  tags TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prompt_library_project ON prompt_library(project_path, archived);
CREATE TABLE IF NOT EXISTS prompt_revisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  prompt_id INTEGER NOT NULL REFERENCES prompt_library(id),
  version INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT NOT NULL,
  tags TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(prompt_id, version)
);

CREATE TABLE IF NOT EXISTS prompt_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_path TEXT NOT NULL,
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(project_path, name)
);

CREATE TABLE IF NOT EXISTS prompt_template_preferences (
  project_path TEXT NOT NULL,
  template_key TEXT NOT NULL,
  category TEXT NOT NULL,
  hidden INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(project_path, template_key)
);

CREATE TABLE IF NOT EXISTS prompt_card_order (
  project_path TEXT NOT NULL,
  card_key TEXT NOT NULL,
  group_name TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(project_path, card_key)
);
CREATE INDEX IF NOT EXISTS idx_prompt_card_order_group
  ON prompt_card_order(project_path, group_name, sort_order);

CREATE INDEX IF NOT EXISTS idx_memory_items_main_area ON memory_items(main_area);
CREATE INDEX IF NOT EXISTS idx_memory_items_category ON memory_items(category);
CREATE INDEX IF NOT EXISTS idx_memory_items_enabled ON memory_items(enabled);
CREATE INDEX IF NOT EXISTS idx_memory_items_project_id ON memory_items(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_versions_item_id ON memory_versions(memory_item_id);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_tool ON prompt_templates(target_tool);
CREATE INDEX IF NOT EXISTS idx_ai_processing_runs_created_at ON ai_processing_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_file_changes_project ON memory_file_changes(project_path, created_at);
"""


TOOL_TEMPLATES = [
    (
        "codex",
        "Codex",
        "輸出適合 Codex 專案協作的 Markdown / AGENTS.md 風格內容。",
        "# Project Instructions\n\n## Context\n{memory}\n\n## Working Rules\n{rules}\n",
    ),
    (
        "chatgpt",
        "通用 ChatGPT",
        "輸出一般對話式完整提示詞。",
        "請根據以下背景協助我：\n\n{memory}\n\n請遵守：\n{rules}\n",
    ),
    (
        "claude",
        "Claude",
        "輸出偏文字協作、上下文清楚的提示詞格式。",
        "<context>\n{memory}\n</context>\n\n<instructions>\n{rules}\n</instructions>\n",
    ),
]


SEED_MEMORY_ITEMS = [
    ("about_me", "personal_background", "科系", "使用者是資訊管理系學生。", "profile"),
    (
        "about_me",
        "technical_skills",
        "目前技術能力",
        "Python 較熟；資料庫、SQL、Excel 會；JavaScript、HTML/CSS 大概看得懂；Git、AI API 有概念。",
        "skills",
    ),
    (
        "about_me",
        "preferences_constraints",
        "主要限制",
        "盡量不要額外花錢；優先本機工具；三個月內完成展示版；避免高維護成本功能。",
        "constraints",
    ),
    (
        "about_me",
        "ai_personality",
        "AI 協作風格",
        "直接、務實、使用繁體中文、優先提供可執行步驟；遇到範圍過大時要指出。",
        "collaboration",
    ),
    (
        "project_memory",
        "project_background",
        "專題主題",
        "AI 個人化管理系統：用圖像化 UI 管理 AI 記憶、提示詞與修改紀錄，並可串接 API 協助壓縮與整理提示內容。",
        "graduation-project",
    ),
    (
        "project_memory",
        "project_requirements",
        "第一版技術方向",
        "macOS 與 Windows 11 桌面 App，使用 Python、pywebview 與 SQLite；核心功能離線可用，AI API 為可選功能。",
        "mvp,tech",
    ),
    (
        "project_memory",
        "decision_record",
        "第一版工具模板",
        "第一版支援 Codex、通用 ChatGPT、Claude 三種輸出模板。",
        "templates",
    ),
]


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    db_path = db_path or get_default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: Path | None = None) -> None:
    db_path = db_path or get_default_db_path()
    with connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        apply_migrations(connection)
        seed_database(connection)


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table_name})")}


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply additive migrations while preserving every v1 table and row."""
    project_columns = _column_names(connection, "projects")
    if "root_path" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN root_path TEXT")
    if "last_scanned_at" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN last_scanned_at TEXT")
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (2, ?, ?)",
        ("AI Memory Manager 2.0 workspace and file change history", utc_now()),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (3, ?, ?)",
        ("Prompt library and immutable prompt revisions", utc_now()),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (4, ?, ?)",
        ("Prompt library groups and drag-to-organize", utc_now()),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (5, ?, ?)",
        ("Project-scoped built-in prompt template preferences", utc_now()),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (6, ?, ?)",
        ("Persistent card order within prompt template groups", utc_now()),
    )


def seed_database(connection: sqlite3.Connection) -> None:
    now = utc_now()

    project_id = connection.execute("SELECT id FROM projects LIMIT 1").fetchone()
    if project_id is None:
        cursor = connection.execute(
            """
            INSERT INTO projects (name, description, status, created_at, updated_at)
            VALUES (?, ?, 'active', ?, ?)
            """,
            (
                "AI 個人化管理系統",
                "畢業專題與個人本機 AI 記憶管理工具。",
                now,
                now,
            ),
        )
        default_project_id = cursor.lastrowid
    else:
        default_project_id = int(project_id["id"])

    for tool_key, display_name, description, template_content in TOOL_TEMPLATES:
        connection.execute(
            """
            INSERT OR IGNORE INTO tool_templates
              (tool_key, display_name, version, description, template_content, source_note, enabled, created_at, updated_at)
            VALUES (?, ?, '1.0', ?, ?, 'built-in seed', 1, ?, ?)
            """,
            (tool_key, display_name, description, template_content, now, now),
        )

    existing_memory_count = connection.execute("SELECT COUNT(*) AS count FROM memory_items").fetchone()[
        "count"
    ]
    if existing_memory_count == 0:
        for main_area, category, title, content, tags in SEED_MEMORY_ITEMS:
            connection.execute(
                """
                INSERT INTO memory_items
                  (project_id, main_area, category, title, content, status, importance, enabled, tags, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'confirmed', 3, 1, ?, 'seed', ?, ?)
                """,
                (default_project_id, main_area, category, title, content, tags, now, now),
            )

    connection.execute(
        """
        INSERT OR IGNORE INTO settings (key, value, value_type, description, updated_at)
        VALUES ('default_output_tool', 'codex', 'text', '預設提示詞輸出格式', ?)
        """,
        (now,),
    )
