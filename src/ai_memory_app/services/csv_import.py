"""Two-phase CSV imports. Preview data stays server-side until committed."""
from __future__ import annotations

import csv
import io
import json
import secrets
import threading
import time

from ..data.database import connect, utc_now
from .agent_catalog import application_root
from .prompt_workbench import validate_text

HEADERS = {
    "prompts": ["title", "content", "group", "tags"],
    "templates": ["tag", "role", "task", "requirements", "output", "acceptance"],
}


class CsvImport:
    def __init__(self, db_path):
        self.db_path = db_path
        self._previews = {}
        self._lock = threading.Lock()

    def catalog(self):
        path = application_root() / "web-ui/data/prompt-template-catalog.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            base = {row["tag"]: row for row in csv.DictReader(handle)}
        with connect(self.db_path) as db:
            base.update({row["tag"]: json.loads(row["payload"]) for row in db.execute("SELECT * FROM user_tag_templates")})
        return list(base.values())

    @staticmethod
    def example(kind):
        if kind not in HEADERS:
            raise ValueError("請選擇提示詞或標籤模板。")
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(HEADERS[kind])
        writer.writerow(
            ["整復店貼文", "# 任務\n撰寫繁體中文社群文案，保留提供的事實。", "行銷", "寫作,行銷"]
            if kind == "prompts" else
            ["社群行銷", "社群編輯", "根據提供的資料規劃貼文", "保留事實|不要捏造療效", "開頭|正文|行動呼籲", "符合品牌語氣|資訊可查證"]
        )
        return "\ufeff" + output.getvalue()

    def preview(self, raw: bytes, kind: str, scope: str):
        if kind not in HEADERS:
            raise ValueError("請選擇提示詞或標籤模板。")
        if len(raw) > 5_000_000:
            raise ValueError("CSV 超過 5 MB，請拆分後匯入。")
        try:
            csv.field_size_limit(200_001)
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
            headers = reader.fieldnames or []
            required = HEADERS[kind][:2 if kind == "prompts" else 3]
            if len(headers) != len(set(headers)) or not set(required).issubset(headers):
                raise ValueError("CSV 欄名不可重複，必要欄位：" + ", ".join(required))
            rows, keys = [], set()
            existing_tags = {item["tag"] for item in self.catalog()} if kind == "templates" else set()
            with connect(self.db_path) as db:
                existing = {(r["category"], r["title"]) for r in db.execute(
                    "SELECT category,title FROM prompt_library WHERE project_path=? AND archived=0", (scope,))}
            for row in reader:
                if len(rows) >= 1000:
                    raise ValueError("每次最多匯入 1,000 筆。")
                line = reader.line_num
                errors = []
                if None in row or any(row.get(key) is None for key in headers):
                    errors.append("欄位數不符")
                data = {key: str(row.get(key) or "").strip() for key in HEADERS[kind]}
                for key in required:
                    if not data[key]:
                        errors.append(f"{key} 不可空白")
                if kind == "prompts":
                    data["group"] = data["group"] or "一般"
                    if len(data["title"]) > 20:
                        errors.append("標題超過 20 字")
                    if len(data["group"]) > 60 or len(data["tags"]) > 500:
                        errors.append("群組超過 60 字或標籤超過 500 字")
                    key = (data["group"], data["title"])
                    duplicate = key in existing
                else:
                    key = data["tag"]
                    duplicate = key in existing_tags
                    if len(key) > 60:
                        errors.append("標籤超過 60 字")
                try:
                    for value in data.values():
                        validate_text(value)
                    if sum(map(len, data.values())) > 200_000:
                        raise ValueError("單筆內容超過 200,000 字元")
                except ValueError as exc:
                    errors.append(str(exc))
                if key in keys:
                    errors.append("CSV 內有重複項目，請移除或取消勾選此筆")
                keys.add(key)
                rows.append({"index": len(rows), "line": line, "data": data, "errors": errors, "duplicate": duplicate})
        except (UnicodeError, csv.Error) as exc:
            line = reader.line_num if 'reader' in locals() else 1
            raise ValueError(f"CSV 第 {line} 行解析失敗，需為 UTF-8 且符合引號與欄位格式。") from exc
        if not rows:
            raise ValueError("CSV 沒有資料列。")
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._previews = {k: v for k, v in self._previews.items() if time.monotonic() - v[0] < 900}
            if len(self._previews) >= 8:
                self._previews.pop(next(iter(self._previews)))
            self._previews[token] = (time.monotonic(), kind, scope, rows)
        return {"preview_id": token, "kind": kind, "scope": scope, "rows": rows}

    def commit(self, preview_id, scope, indices, update=False):
        with self._lock:
            preview = self._previews.get(preview_id)
            if not preview or time.monotonic() - preview[0] >= 900 or scope != preview[2]:
                raise ValueError("預覽已過期或範本庫已切換，請重新選檔。")
            _, kind, _, rows = preview
            if not isinstance(indices, list) or not indices or any(type(i) is not int or not 0 <= i < len(rows) for i in indices):
                raise ValueError("請勾選有效的匯入項目。")
            selected = [rows[i] for i in dict.fromkeys(indices)]
            if any(row["errors"] for row in selected):
                raise ValueError("選取項目含錯誤，尚未寫入任何資料。")
            counts = {"created": 0, "updated": 0, "skipped": 0}
            existing_tags = {r["tag"] for r in self.catalog()} if kind == "templates" else set()
            with connect(self.db_path) as db:
                db.execute("BEGIN IMMEDIATE")
                for row in selected:
                    data, now = row["data"], utc_now()
                    if kind == "templates":
                        exists = data["tag"] in existing_tags
                        if exists and not update:
                            counts["skipped"] += 1
                            continue
                        db.execute("INSERT INTO user_tag_templates VALUES(?,?,?) ON CONFLICT(tag) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                                   (data["tag"], json.dumps(data, ensure_ascii=False), now))
                    else:
                        matches = db.execute("SELECT id,version FROM prompt_library WHERE project_path=? AND category=? AND title=? AND archived=0", (scope, data["group"], data["title"])).fetchall()
                        exists = bool(matches)
                        if exists and not update:
                            counts["skipped"] += 1
                            continue
                        if len(matches) > 1:
                            raise ValueError(f"「{data['title']}」有多筆同名卡片，無法判斷更新目標；整批未寫入。")
                        args = (data["title"], data["content"], data["group"], data["tags"])
                        if exists:
                            item_id, version = matches[0]["id"], matches[0]["version"] + 1
                            db.execute("UPDATE prompt_library SET title=?,content=?,category=?,tags=?,version=?,updated_at=?,document_state='{}' WHERE id=?", (*args, version, now, item_id))
                        else:
                            version = 1
                            item_id = db.execute("INSERT INTO prompt_library(project_path,title,content,category,tags,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (scope, *args, now, now)).lastrowid
                        db.execute("INSERT INTO prompt_revisions(prompt_id,version,title,content,category,tags,created_at) VALUES(?,?,?,?,?,?,?)", (item_id, version, *args, now))
                        db.execute("INSERT OR IGNORE INTO prompt_groups(project_path,name,sort_order,created_at) VALUES(?,?,(SELECT COALESCE(MAX(sort_order),-1)+1 FROM prompt_groups WHERE project_path=?),?)", (scope, data["group"], scope, now))
                    counts["updated" if exists else "created"] += 1
            del self._previews[preview_id]
            return counts
