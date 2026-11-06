from __future__ import annotations

import json
import sys

from .data.database import get_default_db_path, initialize_database
from .data.repository import MemoryRepository
from .services.agent_catalog import application_root
from .services.desktop_api import DesktopApi


def check_document_ai() -> int:
    """Exercise lazy imports and both AI flows inside the packaged interpreter, offline."""
    import io
    from types import SimpleNamespace
    from .services.cloud_advisor import CloudAdvisor
    from .services.document_profiles import profile_fields

    advisor = CloudAdvisor(SimpleNamespace(load=lambda: 'packaging-test-only'))

    def reply(request, **kwargs):
        payload = json.loads(request.data)
        data = json.loads(payload['contents'][0]['parts'][0]['text'])
        if 'answers' in data:
            result = {'fields': {field: '保留已確認內容。' for field in data['field_schema']}}
        else:
            result = {'understanding': ['保留原意。'], 'questions': ['理解是否正確？']}
        return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps(result)}]}}]}).encode())

    advisor._open = reply  # No network, user credentials, database, or paid requests.
    checked = 0
    for kind in ('core', 'memory', 'skill', 'mcp'):
        fields = {item['id']: item['label'] for item in profile_fields(kind, '開發程式', '寫網頁')}
        for mode in ('write', 'revise'):
            field = next(iter(fields))
            request = {'consent': True, 'mode': mode, 'document_type': kind, 'schema_version': 2,
                       'major': '開發程式', 'minor': '寫網頁',
                       'title': '打包檢查', 'field_id': field, 'content': '保留原意。'}
            review = advisor.clarify_document(request)
            result = advisor.compose_document({**request, 'clarification': review, 'answers': ['正確']})
            expected = set(fields) if mode == 'write' else {field}
            if set(result['fields']) != expected:
                raise RuntimeError('Packaged AI flow returned incorrect fields')
            checked += 1
    return checked


def main() -> int:
    """Launch the shared Web UI inside a native desktop window."""
    if "--self-test" in sys.argv:
        import ssl
        context = ssl.create_default_context()
        from .services.agent_catalog import load_agent_catalog
        from .services.prompt_workbench import count_tokens
        report = {
            "tls": context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED,
            "web_ui": (application_root() / "web-ui" / "prompt-workspace.js").exists(),
            "agents": len(load_agent_catalog()["agents"]),
            "document_ai_flows": check_document_ai(),
            "tokenizers": {name: count_tokens("hello world", name) for name in ("o200k_base", "cl100k_base")},
        }
        if "--test-report" in sys.argv:
            from pathlib import Path
            Path(sys.argv[sys.argv.index("--test-report") + 1]).write_text(json.dumps(report), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["tls"] and report["web_ui"] and all(item["exact_text"] for item in report["tokenizers"].values()) else 1
    try:
        import webview
    except ModuleNotFoundError as exc:
        raise SystemExit("pywebview is not installed. Run: pip install -r requirements.txt") from exc

    desktop_check = "--desktop-self-test" in sys.argv
    report_path = None
    if desktop_check:
        from pathlib import Path
        import os
        if not os.environ.get("AI_PROMPT_STUDIO_DATA_DIR"):
            raise RuntimeError("Desktop self-test requires an isolated data directory")
        report_path = Path(sys.argv[sys.argv.index("--desktop-self-test") + 1])

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
    if desktop_check:
        def verify_window():
            import time
            result = {"passed": False}
            try:
                for _ in range(120):
                    ready = window.evaluate_js("Boolean(document.getElementById('documentType-core'))")
                    if ready:
                        result = {"passed": True, "native_window": True, "document_tabs": True}
                        break
                    time.sleep(0.5)
                else:
                    result["error"] = "Document UI did not become ready"
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                report_path.write_text(json.dumps(result), encoding="utf-8")
                window.destroy()
        webview.start(verify_window, debug=False, private_mode=True)
        return 0 if json.loads(report_path.read_text(encoding="utf-8"))["passed"] else 1
    webview.start(debug=False, private_mode=True)
    return 0
