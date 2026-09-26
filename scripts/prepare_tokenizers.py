"""Build-time only: download official tokenizer tables and bundle offline data."""
import base64
import json
from pathlib import Path

import tiktoken

root = Path(__file__).resolve().parents[1] / "resources" / "tokenizers"
root.mkdir(parents=True, exist_ok=True)
for name in ("o200k_base", "cl100k_base"):
    encoding = tiktoken.get_encoding(name)
    data = {"name": name, "source": "https://github.com/openai/tiktoken",
        "pat_str": encoding._pat_str, "special_tokens": encoding._special_tokens,
        "ranks": [[base64.b64encode(token).decode(), rank] for token, rank in encoding._mergeable_ranks.items()]}
    (root / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Prepared {name}: {len(data['ranks'])} ranks")
