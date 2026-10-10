from __future__ import annotations

import json
import sys

from .data.database import get_default_db_path, initialize_database
from .data.repository import MemoryRepository
from .services.agent_catalog import application_root
from .services.desktop_api import DesktopApi


def main() -> int:
    """Launch the shared Web UI inside a native desktop window."""
    if "--self-test" in sys.argv:
        from .services.agent_catalog import load_agent_catalog
        from .services.prompt_workbench import count_tokens
        report = {
            "web_ui": (application_root() / "web-ui" / "prompt-workspace.js").exists(),
            "agents": len(load_agent_catalog()["agents"]),
            "tokenizers": {name: count_tokens("hello world", name) for name in ("o200k_base", "cl100k_base")},
        }
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["web_ui"] and all(item["exact_text"] for item in report["tokenizers"].values()) else 1
    try:
        import webview
    except ModuleNotFoundError as exc:
        raise SystemExit("pywebview is not installed. Run: pip install -r requirements.txt") from exc

    db_path = get_default_db_path()
    initialize_database(db_path)
    repository = MemoryRepository(db_path)
    api = DesktopApi(repository)
    entrypoint = application_root() / "web-ui" / "index.html"
    if not entrypoint.exists():
        raise SystemExit(f"Web UI entrypoint is missing: {entrypoint}")

    window = webview.create_window(
        "AI Prompt Studio · 提示詞視覺化管理",
        str(entrypoint),
        js_api=api,
        width=1440,
        height=900,
        min_size=(980, 680),
        text_select=True,
    )
    api.attach_window(window)
    webview.start(debug=False, private_mode=True)
    return 0
