"""Reproducible synthetic benchmark. Does not measure LLM response quality."""
import json
from pathlib import Path
from ai_memory_app.services.prompt_workbench import analyze_prompt

cases = [
    ("zh_duplicate", "## 任務\n\n請審查程式。\n\n\n- 保留原始需求與介面。\n- 保留原始需求與介面。\n\n## 輸出格式\n\n問題與驗證方法。\n"),
    ("en_duplicate", "You are a reviewer.\n\n\nTask: review this function.\n- Preserve the public API.\n- Preserve the public API.\nOutput: findings and tests.\n"),
    ("code_preservation", "請說明以下程式。\n\n```python\nprint('hello')\n\n\nprint('hello')\n```\n"),
    ("already_concise", "請用三點摘要以下文字，保留數字與日期。\n"),
    ("mixed_language", "請 review {{code}}。\n\n\n- Output JSON only.\n- Output JSON only.\n"),
]
rows = []
for name, text in cases:
    for encoding in ("o200k_base", "cl100k_base"):
        result = analyze_prompt({"content": text, "encoding": encoding, "remove_duplicates": True})
        rows.append({"case": name, "encoding": encoding, "before": result["before"]["count"], "after": result["after"]["count"], "saved_percent": result["saved_percent"], "changes": len(result["changes"]), "exact_text": result["before"]["exact_text"]})
destination = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "token-benchmark.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps({"dataset": "synthetic-v1", "quality_tested": False, "scope": "Five illustrative texts, not representative of real-world savings", "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(rows, ensure_ascii=False, indent=2))
