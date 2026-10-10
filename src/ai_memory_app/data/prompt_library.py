from __future__ import annotations

from .database import connect, utc_now
from ..services.prompt_workbench import validate_text


class PromptLibrary:
    DEFAULT_GROUP = "一般"

    def __init__(self, db_path):
        self.db_path = db_path

    def list(self, project_path: str, query: str = "", category: str = "", archived: bool = False) -> list[dict]:
        with connect(self.db_path) as db:
            rows = db.execute("SELECT * FROM prompt_library WHERE project_path = ? AND archived = ? ORDER BY updated_at DESC, id DESC", (project_path, int(archived))).fetchall()
        query = query.casefold()
        return [dict(row) for row in rows if (not category or row["category"] == category) and
                (not query or query in " ".join(str(row[key]) for key in ("title", "content", "tags", "category")).casefold())]

    def save(self, project_path: str, request: dict) -> dict:
        title = str(request.get("title", "")).strip()
        content = validate_text(request.get("content", ""))
        if not title or len(title) > 20 or not content.strip():
            raise ValueError("請填寫 1–20 字的標題與非空白內容。")
        category = str(request.get("category", "一般"))[:100]
        tags = str(request.get("tags", ""))[:500]
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            item_id = request.get("id")
            now = utc_now()
            version = 1
            if item_id:
                old = db.execute("SELECT * FROM prompt_library WHERE id = ? AND project_path = ?", (item_id, project_path)).fetchone()
                if not old or old["version"] != request.get("version"):
                    raise ValueError("提示詞版本已變更，請重新開啟後儲存。")
                version = old["version"] + 1
                db.execute("UPDATE prompt_library SET title=?, content=?, category=?, tags=?, version=?, archived=?, updated_at=? WHERE id=?", (title, content, category, tags, version, int(bool(request.get("archived", False))), now, item_id))
            else:
                item_id = db.execute("INSERT INTO prompt_library(project_path,title,content,category,tags,version,archived,created_at,updated_at) VALUES(?,?,?,?,?,1,0,?,?)", (project_path, title, content, category, tags, now, now)).lastrowid
            db.execute("INSERT INTO prompt_revisions(prompt_id,version,title,content,category,tags,created_at) VALUES(?,?,?,?,?,?,?)", (item_id, version, title, content, category, tags, now))
            return dict(db.execute("SELECT * FROM prompt_library WHERE id=?", (item_id,)).fetchone())

    def history(self, project_path: str, item_id: int) -> list[dict]:
        with connect(self.db_path) as db:
            return [dict(row) for row in db.execute("SELECT r.* FROM prompt_revisions r JOIN prompt_library p ON p.id=r.prompt_id WHERE p.project_path=? AND p.id=? ORDER BY r.version DESC", (project_path, item_id)).fetchall()]

    def groups(self, project_path: str) -> list[dict]:
        with connect(self.db_path) as db:
            explicit = [dict(row) for row in db.execute(
                "SELECT name, sort_order FROM prompt_groups WHERE project_path=? ORDER BY sort_order, name COLLATE NOCASE",
                (project_path,),
            ).fetchall()]
            used = [str(row["category"]) for row in db.execute(
                "SELECT DISTINCT category FROM prompt_library WHERE project_path=? AND archived=0 ORDER BY category COLLATE NOCASE",
                (project_path,),
            ).fetchall()]
            used.extend(str(row["category"]) for row in db.execute(
                "SELECT DISTINCT category FROM prompt_template_preferences WHERE project_path=? AND hidden=0 ORDER BY category COLLATE NOCASE",
                (project_path,),
            ).fetchall())
        names = [item["name"] for item in explicit]
        for name in used:
            if name not in names:
                names.append(name)
        if self.DEFAULT_GROUP not in names:
            names.append(self.DEFAULT_GROUP)
        return [{"name": name, "sort_order": index} for index, name in enumerate(names)]

    def create_group(self, project_path: str, name: str) -> dict:
        name = str(name or "").strip()
        if not 1 <= len(name) <= 60:
            raise ValueError("群組名稱請填寫 1–60 字。")
        with connect(self.db_path) as db:
            existing = db.execute("SELECT 1 FROM prompt_groups WHERE project_path=? AND name=?", (project_path, name)).fetchone()
            if existing:
                raise ValueError("已有相同名稱的群組。")
            order = db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS value FROM prompt_groups WHERE project_path=?", (project_path,)).fetchone()["value"]
            now = utc_now()
            db.execute("INSERT INTO prompt_groups(project_path,name,sort_order,created_at) VALUES(?,?,?,?)", (project_path, name, order, now))
        return {"name": name, "sort_order": order}

    def move_to_group(self, project_path: str, item_id: int, group_name: str) -> dict:
        group_name = str(group_name or "").strip()
        if not 1 <= len(group_name) <= 60:
            raise ValueError("群組名稱請填寫 1–60 字。")
        with connect(self.db_path) as db:
            item = db.execute("SELECT * FROM prompt_library WHERE id=? AND project_path=?", (item_id, project_path)).fetchone()
            if item is None:
                raise ValueError("找不到要移動的提示詞。")
            if not db.execute("SELECT 1 FROM prompt_groups WHERE project_path=? AND name=?", (project_path, group_name)).fetchone():
                order = db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS value FROM prompt_groups WHERE project_path=?", (project_path,)).fetchone()["value"]
                db.execute("INSERT INTO prompt_groups(project_path,name,sort_order,created_at) VALUES(?,?,?,?)", (project_path, group_name, order, utc_now()))
            db.execute("UPDATE prompt_library SET category=?, updated_at=? WHERE id=?", (group_name, utc_now(), item_id))
            return dict(db.execute("SELECT * FROM prompt_library WHERE id=?", (item_id,)).fetchone())

    def template_preferences(self, project_path: str) -> list[dict]:
        with connect(self.db_path) as db:
            return [dict(row) for row in db.execute(
                "SELECT template_key, category, hidden, updated_at FROM prompt_template_preferences WHERE project_path=? ORDER BY template_key",
                (project_path,),
            ).fetchall()]

    def card_order(self, project_path: str) -> list[dict]:
        with connect(self.db_path) as db:
            return [dict(row) for row in db.execute(
                "SELECT card_key, group_name, sort_order, updated_at FROM prompt_card_order "
                "WHERE project_path=? ORDER BY group_name COLLATE NOCASE, sort_order, card_key",
                (project_path,),
            ).fetchall()]

    def place_card(self, project_path: str, card_key: str, group_name: str, ordered_card_keys: list[str]) -> dict:
        card_key = str(card_key or "").strip()
        group_name = str(group_name or "").strip()
        ordered_card_keys = list(dict.fromkeys(str(key).strip() for key in (ordered_card_keys or []) if str(key).strip()))
        if not 1 <= len(group_name) <= 60:
            raise ValueError("群組名稱請填寫 1–60 字。")
        if not card_key or card_key not in ordered_card_keys or any(len(key) > 100 for key in ordered_card_keys):
            raise ValueError("卡片排序資料不正確。")
        prefix, separator, identifier = card_key.partition(":")
        if not separator or prefix not in {"prompt", "template"} or not identifier:
            raise ValueError("卡片識別碼不正確。")
        now = utc_now()
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM prompt_groups WHERE project_path=? AND name=?", (project_path, group_name)).fetchone():
                order = db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS value FROM prompt_groups WHERE project_path=?", (project_path,)).fetchone()["value"]
                db.execute("INSERT INTO prompt_groups(project_path,name,sort_order,created_at) VALUES(?,?,?,?)", (project_path, group_name, order, now))
            if prefix == "prompt":
                if not identifier.isdigit():
                    raise ValueError("找不到要移動的提示詞。")
                moved = db.execute(
                    "UPDATE prompt_library SET category=?, updated_at=? WHERE id=? AND project_path=?",
                    (group_name, now, int(identifier), project_path),
                ).rowcount
                if not moved:
                    raise ValueError("找不到要移動的提示詞。")
            else:
                if len(identifier) > 80:
                    raise ValueError("找不到要移動的內建範本。")
                db.execute(
                    "INSERT INTO prompt_template_preferences(project_path,template_key,category,hidden,updated_at) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(project_path,template_key) DO UPDATE SET category=excluded.category,hidden=0,updated_at=excluded.updated_at",
                    (project_path, identifier, group_name, 0, now),
                )
            for index, key in enumerate(ordered_card_keys):
                db.execute(
                    "INSERT INTO prompt_card_order(project_path,card_key,group_name,sort_order,updated_at) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(project_path,card_key) DO UPDATE SET group_name=excluded.group_name,sort_order=excluded.sort_order,updated_at=excluded.updated_at",
                    (project_path, key, group_name, index, now),
                )
        return {"card_key": card_key, "group_name": group_name, "ordered_card_keys": ordered_card_keys}

    def set_template_preference(self, project_path: str, template_key: str, category: str, hidden: bool = False) -> dict:
        template_key = str(template_key or "").strip()
        category = str(category or "").strip()
        if not 1 <= len(template_key) <= 80:
            raise ValueError("找不到要更新的內建範本。")
        if not 1 <= len(category) <= 60:
            raise ValueError("群組名稱請填寫 1–60 字。")
        now = utc_now()
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM prompt_groups WHERE project_path=? AND name=?", (project_path, category)).fetchone():
                order = db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS value FROM prompt_groups WHERE project_path=?", (project_path,)).fetchone()["value"]
                db.execute("INSERT INTO prompt_groups(project_path,name,sort_order,created_at) VALUES(?,?,?,?)", (project_path, category, order, now))
            db.execute(
                "INSERT INTO prompt_template_preferences(project_path,template_key,category,hidden,updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(project_path,template_key) DO UPDATE SET category=excluded.category,hidden=excluded.hidden,updated_at=excluded.updated_at",
                (project_path, template_key, category, int(bool(hidden)), now),
            )
        return {"template_key": template_key, "category": category, "hidden": bool(hidden), "updated_at": now}

    def reset_template_preferences(self, project_path: str) -> dict:
        with connect(self.db_path) as db:
            removed = db.execute("DELETE FROM prompt_template_preferences WHERE project_path=?", (project_path,)).rowcount
        return {"reset": True, "removed": removed}

    def delete_group(self, project_path: str, name: str, builtin_template_keys: list[str] | None = None) -> dict:
        name = str(name or "").strip()
        if not name or name == self.DEFAULT_GROUP:
            raise ValueError("「一般」是預設群組，不能刪除。")
        builtin_template_keys = list(dict.fromkeys(str(key).strip() for key in (builtin_template_keys or []) if str(key).strip()))
        if any(len(key) > 80 for key in builtin_template_keys):
            raise ValueError("內建範本識別碼不正確。")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            exists = db.execute(
                "SELECT 1 FROM prompt_groups WHERE project_path=? AND name=? "
                "UNION SELECT 1 FROM prompt_library WHERE project_path=? AND category=? "
                "UNION SELECT 1 FROM prompt_template_preferences WHERE project_path=? AND category=? LIMIT 1",
                (project_path, name, project_path, name, project_path, name),
            ).fetchone()
            if not exists and not builtin_template_keys:
                raise ValueError("找不到要刪除的群組。")
            moved = db.execute(
                "UPDATE prompt_library SET category=?, updated_at=? WHERE project_path=? AND category=?",
                (self.DEFAULT_GROUP, utc_now(), project_path, name),
            ).rowcount
            now = utc_now()
            stored_keys = [str(row["template_key"]) for row in db.execute(
                "SELECT template_key FROM prompt_template_preferences WHERE project_path=? AND category=?",
                (project_path, name),
            ).fetchall()]
            moved_keys = list(dict.fromkeys(stored_keys + builtin_template_keys))
            for key in moved_keys:
                db.execute(
                    "INSERT INTO prompt_template_preferences(project_path,template_key,category,hidden,updated_at) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(project_path,template_key) DO UPDATE SET category=excluded.category,updated_at=excluded.updated_at",
                    (project_path, key, self.DEFAULT_GROUP, 0, now),
                )
            append_after = db.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS value FROM prompt_card_order WHERE project_path=? AND group_name=?",
                (project_path, self.DEFAULT_GROUP),
            ).fetchone()["value"]
            db.execute(
                "UPDATE prompt_card_order SET group_name=?,sort_order=sort_order+?,updated_at=? WHERE project_path=? AND group_name=?",
                (self.DEFAULT_GROUP, append_after, now, project_path, name),
            )
            db.execute("DELETE FROM prompt_groups WHERE project_path=? AND name=?", (project_path, name))
        return {"name": name, "moved_prompts": moved, "moved_templates": len(moved_keys), "fallback_group": self.DEFAULT_GROUP}

    def delete(self, project_path: str, item_id: int) -> dict:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute(
                "SELECT id, title FROM prompt_library WHERE id=? AND project_path=?",
                (item_id, project_path),
            ).fetchone()
            if item is None:
                raise ValueError("找不到要刪除的提示詞。")
            db.execute("DELETE FROM prompt_revisions WHERE prompt_id=?", (item_id,))
            db.execute("DELETE FROM prompt_library WHERE id=? AND project_path=?", (item_id, project_path))
            db.execute("DELETE FROM prompt_card_order WHERE project_path=? AND card_key=?", (project_path, f"prompt:{item_id}"))
        return {"id": int(item["id"]), "title": item["title"], "deleted": True}
