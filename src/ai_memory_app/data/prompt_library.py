from __future__ import annotations

from .database import connect, utc_now
from ..services.prompt_workbench import validate_text


class PromptLibrary:
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
