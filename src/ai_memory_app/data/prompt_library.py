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
        if not title or len(title) > 200 or not content.strip():
            raise ValueError("請填寫 1–200 字的標題與非空白內容。")
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
