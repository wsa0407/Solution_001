from __future__ import annotations

import json
import os
from typing import Any

from solution_gen.config import settings
from solution_gen.workers.prose import is_chapter_prose, is_exportable_body

_HARNESS_ONLY_MODELS = ("flash", "deepseek-v4")


def _chat_model(name: str) -> str:
    raw = (name or "").strip()
    if not raw or any(tag in raw.lower() for tag in _HARNESS_ONLY_MODELS):
        return "deepseek-chat"
    return raw


async def complete(prompt: str, *, max_tokens: int = 2048) -> tuple[str | None, int]:
    """返回 (正文, token估算)。只走 chat/completions，不跑 Harness agent loop。"""
    for key, base, model in (
        (
            settings.deepseek_api_key,
            settings.deepseek_base_url or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com",
            _chat_model(settings.deepseek_model),
        ),
        (
            settings.llm_api_key,
            settings.llm_base_url or os.environ.get("MINIMAX_BASE_URL") or "https://api.minimaxi.com/v1",
            settings.llm_model,
        ),
    ):
        if not key:
            continue
        text, tokens = await _chat_completions(base, key, model, prompt, max_tokens)
        if is_exportable_body(text):
            return text, tokens
    return None, 0


async def _chat_completions(
    base: str, key: str, model: str, prompt: str, max_tokens: int
) -> tuple[str | None, int]:
    try:
        import httpx
    except ImportError:
        return None, 0
    url = base.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                str(part.get("text") or "") for part in content if isinstance(part, dict) and part.get("type") == "text"
            ) or "".join(str(part) for part in content)
        text = str(content or "").strip()
        if not is_chapter_prose(text):
            return None, 0
        usage = data.get("usage") or {}
        tokens = int(usage.get("total_tokens") or len(text))
        return text, tokens
    except Exception:
        return None, 0


def parse_json_block(text: str) -> Any | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    i, j = text.find("["), text.rfind("]")
    if i >= 0 and j > i:
        try:
            return json.loads(text[i : j + 1])
        except json.JSONDecodeError:
            return None
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(text[i : j + 1])
        except json.JSONDecodeError:
            return None
    return None
