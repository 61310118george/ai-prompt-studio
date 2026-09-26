# AI Memory Manager 2.0 SQLite 資料模型

## 原則

- 所有 1.x 表格與資料保留。
- 2.0 只做 additive migration。
- 使用 `schema_migrations` 記錄資料庫版本。
- Markdown 正文仍以專案檔案為準，SQLite 只記錄 App 資料與變更歷史。

## 既有表格

```text
settings
projects
memory_items
memory_versions
prompt_templates
tool_templates
ai_processing_runs
exports
```

## 2.0 migration

`projects` 新增：

```text
root_path TEXT NULL
last_scanned_at TEXT NULL
```

新增：

```sql
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE memory_file_changes (
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
```

## `memory_file_changes` 用途

- `base_hash`：預覽所依據的原始檔 SHA-256。
- `output_hash`：成功寫回內容的 SHA-256。
- `diff_text`：當次 unified diff。
- `backup_path`：Application Support 備份路徑；新檔可為空。
- `original_existed`：復原時決定還原備份或移除新檔。
- `status`：`applied` 或 `restored`。

App 不在 SQLite 保存 API Key，也不把整份專案 Markdown 複製成第二個真相來源。
