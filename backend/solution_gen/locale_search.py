"""属地政策检索。写章时按属地过滤；默认走 DeepSeek 原生 web_search。"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from solution_gen.config import settings
from solution_gen.domain import Chapter, Citation, Job, Profile
from solution_gen.rag import place_key

LOCALE_WRITING = frozenset({"overview", "background", "initiation_basis"})
LOCALE_TITLE_HINTS = ("概述", "背景", "立项依据")
MAX_HITS = 5

SearchFn = Callable[[str], list["SearchHit"]]

_provider: SearchFn | None = None


@dataclass(frozen=True)
class SearchHit:
    title: str
    excerpt: str = ""
    url: str = ""


def set_search_provider(fn: SearchFn | None) -> None:
    global _provider
    _provider = fn


def needs_locale_policy(chapter: Chapter) -> bool:
    if chapter.writing in LOCALE_WRITING:
        return True
    return any(hint in (chapter.title or "") for hint in LOCALE_TITLE_HINTS)


def locale_queries(profile: Profile) -> list[str]:
    place = (profile.place or "").strip()
    industry = (profile.industry or "产业").strip()
    if not place:
        return []
    return [
        f"{place} {industry} 发展规划",
        f"{place} {industry} 政策",
        f"{place} 国民经济和社会发展 规划",
    ]


def matches_place(hit: SearchHit, place: str) -> bool:
    blob = f"{hit.title} {hit.excerpt} {hit.url}"
    if place and place in blob:
        return True
    pk = place_key(place)
    return bool(pk) and pk in blob


def search_locale_policy(profile: Profile) -> list[Citation]:
    queries = locale_queries(profile)
    if not queries:
        return []
    if _provider is not None:
        raw_hits: list[SearchHit] = []
        for query in queries:
            raw_hits.extend(_provider(query))
    else:
        raw_hits = _deepseek_provider("；".join(queries), profile.place)
    seen: set[str] = set()
    out: list[Citation] = []
    why = queries[0]
    for hit in raw_hits:
        title = (hit.title or "").strip()
        if not title or title in seen:
            continue
        if not matches_place(hit, profile.place):
            continue
        seen.add(title)
        out.append(
            Citation(
                library="检索",
                title=title,
                why=why,
                excerpt=(hit.excerpt or "")[:240],
                url=hit.url or "",
            )
        )
        if len(out) >= MAX_HITS:
            return out
    return out


def fill_locale_search(job: Job) -> list[Citation]:
    if job.locale_searched:
        return [c for c in job.citations if c.library == "检索"]
    job.locale_searched = True
    if not job.profile:
        return []
    pending = [c for c in job.chapters if c.status != "done" and needs_locale_policy(c)]
    if not pending:
        return []
    hits = search_locale_policy(job.profile)
    existing = {c.title for c in job.citations}
    for hit in hits:
        if hit.title not in existing:
            job.citations.append(hit)
            existing.add(hit.title)
    return hits


def locale_prompt_block(job: Job, chapter: Chapter) -> str:
    if not needs_locale_policy(chapter):
        return ""
    lib = [c for c in job.citations if c.library == "地方库"]
    web = [c for c in job.citations if c.library == "检索"]
    lines = [
        "地方政策摘录（属地库优先，检索为辅）。地方文件名必须出自下列 title，禁止写「XX市相关规划」「有关部门文件」。",
    ]
    for c in (lib + web)[:8]:
        url = f" {c.url}" if c.url else ""
        lines.append(f"- [{c.library}] {c.title}:{url} {c.excerpt}".rstrip())
    if not lib and not web:
        lines.append(
            "地方检索无命中，禁止编造文件名；可写未见公开专项规划，只引用国家/行业政策。"
        )
    return "\n".join(lines) + "\n"


def _search_model() -> str:
    raw = (settings.deepseek_model or "").strip().lower()
    if "pro" in raw:
        return "deepseek-v4-pro"
    return "deepseek-v4-flash"


def _deepseek_provider(query: str, place: str) -> list[SearchHit]:
    key = (settings.deepseek_api_key or "").strip()
    if not key:
        return []
    base = (settings.deepseek_base_url or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    prompt = (
        f"用网页检索查找与下列问题相关的公开政策、规划、政府文件。"
        f"只保留属地「{place}」的文件，不要外市文件。"
        f"查询：{query}\n"
        f"输出 JSON：{{\"results\":[{{\"title\":\"文件全称\",\"excerpt\":\"一两句摘要\",\"url\":\"来源链接\"}}]}}"
    )
    payload: dict[str, Any] = {
        "model": _search_model(),
        "input": prompt,
        "tools": [{"type": "web_search"}],
        "tool_choice": {"type": "web_search"},
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1200,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=60.0) as client:
            res = client.post(base + "/responses", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
    except Exception:
        return []
    return hits_from_deepseek_response(data)


def _parse_json(text: str) -> Any | None:
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
            pass
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(text[i : j + 1])
        except json.JSONDecodeError:
            return None
    return None


def hits_from_deepseek_response(data: dict[str, Any]) -> list[SearchHit]:
    texts: list[str] = []
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        texts.append(data["output_text"])
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            texts.append(content)
            continue
        for part in content or []:
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                texts.append(str(part.get("text") or ""))
    blob = "\n".join(texts).strip()
    parsed = _parse_json(blob) if blob else None
    rows: list[Any] = []
    if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
        rows = parsed["results"]
    elif isinstance(parsed, list):
        rows = parsed
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        hits.append(
            SearchHit(
                title=title,
                excerpt=str(row.get("excerpt") or row.get("content") or row.get("snippet") or "")[:240],
                url=str(row.get("url") or ""),
            )
        )
        if len(hits) >= MAX_HITS:
            break
    return hits
