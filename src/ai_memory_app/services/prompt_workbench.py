"""Offline prompt analysis. No model requests and no runtime downloads."""
from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
from functools import lru_cache

from .agent_catalog import application_root

MAX_PROMPT_CHARS = 200_000


def validate_text(text: object) -> str:
    if not isinstance(text, str) or len(text) > MAX_PROMPT_CHARS:
        raise ValueError("提示詞必須是文字，且不得超過 200,000 字元。")
    return text


@lru_cache(maxsize=2)
def _encoding(name: str):
    import base64
    import tiktoken
    path = application_root() / "resources" / "tokenizers" / f"{name}.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    return tiktoken.Encoding(name=name, pat_str=spec["pat_str"],
        mergeable_ranks={base64.b64decode(token): rank for token, rank in spec["ranks"]},
        special_tokens=spec["special_tokens"])


def count_tokens(text: str, encoding: str = "o200k_base") -> dict:
    validate_text(text)
    if encoding not in {"o200k_base", "cl100k_base", "estimate"}:
        raise ValueError("不支援的 tokenizer。")
    if encoding != "estimate":
        try:
            count = len(_encoding(encoding).encode(text, disallowed_special=()))
            return {"count": count, "method": encoding, "exact_text": True,
                    "note": "本機 tokenizer 的純文字計數；不含訊息封裝、工具、圖片或輸出。"}
        except (ImportError, OSError, ValueError, KeyError):
            pass
    count = math.ceil(sum(1 if ord(char) < 128 else 4 for char in text) / 4)
    return {"count": count, "method": "heuristic", "exact_text": False,
            "note": "粗估值：英文約 4 字元、非 ASCII 約 1 字元／token；不是任何模型的精確帳單。"}


def _compact(text: str, remove_duplicates: bool) -> tuple[str, list[dict]]:
    output: list[str] = []
    changes: list[dict] = []
    fence: tuple[str, int] | None = None
    previous_bullet = ""
    for index, raw in enumerate(text.splitlines(keepends=True)):
        line = raw.rstrip("\r\n")
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            output.append(raw)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not line[marker.end():].strip():
                fence = None
            previous_bullet = ""
            continue
        if marker:
            fence = (marker[1][0], len(marker[1]))
            output.append(raw)
            previous_bullet = ""
            continue
        if not line.strip() and output and not output[-1].strip():
            changes.append({"line": index + 1, "rule": "blank_lines", "detail": "移除連續多餘空白行"})
            continue
        bullet = line if re.match(r"^[-*+] \S", line) else ""
        if remove_duplicates and bullet and bullet == previous_bullet:
            changes.append({"line": index + 1, "rule": "adjacent_duplicate", "detail": "移除相鄰完全相同條列；需確認重複不是刻意強調"})
            continue
        output.append(raw)
        previous_bullet = bullet
    return "".join(output), changes


def analyze_prompt(request: dict) -> dict:
    text = validate_text(request.get("content", ""))
    encoding = request.get("encoding", "o200k_base")
    price = request.get("input_price")
    calls = request.get("calls", 1)
    if isinstance(calls, bool) or not isinstance(calls, int) or not 1 <= calls <= 10_000_000:
        raise ValueError("呼叫次數須為 1 到 10,000,000 的整數。")
    if price is not None:
        if isinstance(price, bool) or not isinstance(price, (float, int)) or not math.isfinite(price) or not 0 <= price <= 1_000_000:
            raise ValueError("輸入單價須為有效的非負數（USD／百萬 token）。")
    candidate, changes = _compact(text, bool(request.get("remove_duplicates", False)))
    before = count_tokens(text, encoding)
    after = count_tokens(candidate, encoding)
    warnings = ["格式精簡不代表回答品質提升。請保留必要條件並比較任務結果。"]
    if after["count"] > before["count"]:
        warnings.append("此 tokenizer 下精簡反而增加 token，已保留原文。")
        candidate, after, changes = text, before.copy(), []
    savings = before["count"] - after["count"]
    for key, pattern in (("角色", r"角色|你是|you are"), ("任務", r"任務|請|task|please"), ("輸出格式", r"格式|輸出|format|output")):
        if not re.search(pattern, text, re.I):
            warnings.append(f"未辨識到明確的{key}說明；這是關鍵字提示，不是品質評分。")
    if re.search(r"\bsk-[A-Za-z0-9_-]{20,}|\bgh[pousr]_[A-Za-z0-9]{20,}|PRIVATE KEY|(?:password|密碼)\s*[:=]\s*\S+", text, re.I):
        warnings.append("可能含有憑證或密碼，複製到外部 AI 前請檢查。")
    return {
        "original": text, "candidate": candidate, "before": before, "after": after,
        "saved_tokens": savings, "saved_percent": round(savings * 100 / before["count"], 2) if before["count"] else 0,
        "changes": changes, "warnings": warnings, "base_hash": hashlib.sha256(text.encode()).hexdigest(),
        "diff": "\n".join(difflib.unified_diff(text.splitlines(), candidate.splitlines(), fromfile="原文", tofile="精簡候選", lineterm="")),
        "cost": None if price is None else {
            "currency": "USD", "input_price_per_million": price, "calls": calls,
            "before": before["count"] * price * calls / 1_000_000,
            "after": after["count"] * price * calls / 1_000_000,
            "saved": savings * price * calls / 1_000_000,
            "basis": "使用者輸入單價的未快取純文字輸入情境；不含輸出、稅或其他費用，非實際帳單。",
        },
    }
