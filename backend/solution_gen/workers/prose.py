"""章节正文过滤器。禁止把 Harness RunResult / 推理过程写进 Word。"""

from __future__ import annotations

import re
from typing import Any

from solution_gen.workers.numbering import normalize_chapter_numbering

_DUMP_MARKERS = (
    "RunResult(",
    "session_id=",
    "'type': 'assistant/chunk'",
    '"type": "assistant/chunk"',
    "agent/inbox/spliced",
    "finish_reason=",
)
_GUIDE_MARKERS = (
    "写概述，覆盖",
    "写建设背景",
    "写需求分析",
    "写建设方案",
    "文类写法",
    "只输出本章中文正文",
    "写作要点:",
)


def is_chapter_prose(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    head = raw[:800]
    return not any(marker in head for marker in _DUMP_MARKERS)


def is_exportable_body(text: str | None) -> bool:
    if not is_chapter_prose(text):
        return False
    head = (text or "").strip()[:400]
    return not any(marker in head for marker in _GUIDE_MARKERS)


def chapter_export_text(
    content: str | None,
    fallback: str = "",
    *,
    index: int | None = None,
    title: str = "",
) -> str:
    raw = ""
    if is_exportable_body(content):
        raw = (content or "").strip()
    elif is_exportable_body(fallback):
        raw = (fallback or "").strip()
    if index and raw:
        raw = normalize_chapter_numbering(raw, index, title)
    return "\n".join(_plain_lines(raw))


def _plain_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line or set(line) <= {"-", "*", "_", "="}:
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"__(.+?)__", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = line.replace("**", "").replace("__", "")
        line = re.sub(r"^[-*]\s+", "", line)
        if line:
            lines.append(line)
    return lines


def extract_model_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip() if is_chapter_prose(result) else ""
    text = _as_text(getattr(result, "final_response", None))
    if is_chapter_prose(text):
        return text
    events = getattr(result, "events", None)
    if isinstance(events, list):
        text = _text_from_events(events)
        if is_chapter_prose(text):
            return text
    for attr in ("text", "content", "output"):
        text = _as_text(getattr(result, attr, None))
        if is_chapter_prose(text):
            return text
    return ""


def _as_text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def _text_from_events(events: list[Any]) -> str:
    for event in reversed(events):
        if not isinstance(event, dict) or event.get("type") != "assistant/message":
            continue
        joined = _text_blocks(_message_content(event))
        if joined.strip():
            return joined.strip()
    parts: list[str] = []
    for event in events:
        if not isinstance(event, dict) or event.get("type") != "assistant/chunk":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        chunk = data.get("chunk") if isinstance(data.get("chunk"), dict) else {}
        if chunk.get("type") in {"text-delta", "output-delta"}:
            parts.append(str(chunk.get("text") or ""))
    return "".join(parts).strip()


def _message_content(event: dict[str, Any]) -> list[Any]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    owner = message or data
    content = owner.get("content")
    return content if isinstance(content, list) else []


def _text_blocks(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return "".join(parts)
