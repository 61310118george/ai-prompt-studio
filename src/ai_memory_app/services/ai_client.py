from __future__ import annotations

import json
import urllib.error
import urllib.request


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class AIClientError(RuntimeError):
    pass


def organize_with_openai(*, api_key: str, model: str, source_text: str, output_format: str) -> str:
    prompt = (
        "你是一個 AI 記憶與提示詞管理系統的整理器。請把使用者輸入整理成精簡、結構化、可保存的內容。"
        "請使用繁體中文。"
        f"\n\n目標輸出格式：{output_format}"
        "\n\n請輸出：\n"
        "1. 摘要\n"
        "2. 建議分類\n"
        "3. 可保存記憶條目\n"
        "4. 可直接給 AI 使用的精簡提示詞\n"
        f"\n\n原始內容：\n{source_text}"
    )
    payload = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AIClientError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AIClientError(f"OpenAI API 連線失敗：{exc.reason}") from exc

    text = _extract_response_text(data)
    if not text:
        raise AIClientError("OpenAI API 回應中沒有可讀文字。")
    return text


def revise_markdown_with_openai(
    *,
    api_key: str,
    model: str,
    markdown_text: str,
    instruction: str,
    file_name: str,
) -> str:
    prompt = (
        "你是一個精準修改 Markdown 記憶檔的助理。"
        "請根據使用者指令修改 Markdown 全文。"
        "只輸出修改後的完整 Markdown 內容，不要加解釋、不要包 code block。"
        "請保留原本仍然正確的資訊，不要擅自刪除未要求刪除的內容。"
        f"\n\n檔名：{file_name}"
        f"\n\n修改指令：\n{instruction}"
        f"\n\n原始 Markdown：\n{markdown_text}"
    )
    payload = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AIClientError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AIClientError(f"OpenAI API 連線失敗：{exc.reason}") from exc

    text = _extract_response_text(data).strip()
    if not text:
        raise AIClientError("OpenAI API 回應中沒有可讀 Markdown。")
    return _strip_markdown_fence(text)


def _extract_response_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    chunks: list[str] = []
    for output_item in data.get("output", []) or []:
        for content_item in output_item.get("content", []) or []:
            if isinstance(content_item.get("text"), str):
                chunks.append(content_item["text"])
    return "\n".join(chunks).strip()


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped
