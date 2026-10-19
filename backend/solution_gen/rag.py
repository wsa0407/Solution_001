from __future__ import annotations

import json
from pathlib import Path

from solution_gen.config import settings
from solution_gen.domain import Citation, Profile


def _iter_docs() -> list[dict]:
    docs: list[dict] = []
    root = settings.knowledge_dir
    if not root.exists():
        return docs
    for path in root.rglob("*.json"):
        docs.append(json.loads(path.read_text(encoding="utf-8")))
    return docs


def place_key(place: str) -> str:
    return (place or "").replace("市", "").replace("县", "").replace("区", "")


def _place_key(place: str) -> str:
    return place_key(place)


def retrieve(profile: Profile, query: str, k: int = 6) -> list[Citation]:
    """产品库优先 → 风格库 → 地方库；地方库强制属地过滤。"""
    docs = _iter_docs()
    scored: list[tuple[int, dict]] = []
    q = query + " " + profile.industry + " " + profile.need
    pk = _place_key(profile.place)
    for doc in docs:
        lib = doc.get("library", "")
        place = doc.get("place") or ""
        if lib == "地方库" and pk and _place_key(place) not in {pk, ""} and pk not in place:
            continue
        if lib == "地方库" and pk and _place_key(place) and _place_key(place) != pk and pk not in place:
            continue
        if lib == "地方库" and pk and place and pk not in place and profile.place not in place:
            continue
        score = 0
        industry = doc.get("industry") or ""
        if industry and industry in profile.industry:
            score += 5
        if lib == "产品库":
            score += 3
        elif lib == "地方库":
            score += 4 if pk and (pk in place or profile.place in place) else 0
        text = (doc.get("title") or "") + (doc.get("text") or "")
        for token in q:
            if token and token in text:
                score += 1
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[Citation] = []
    seen = set()
    for _, doc in scored:
        title = doc.get("title") or ""
        if title in seen:
            continue
        seen.add(title)
        out.append(
            Citation(
                library=doc.get("library") or "产品库",
                title=title,
                why="自动检索",
                excerpt=(doc.get("text") or "")[:240],
            )
        )
        if len(out) >= k:
            break
    return out


def canonical_params() -> dict[str, str]:
    params: dict[str, str] = {}
    for doc in _iter_docs():
        if doc.get("library") == "产品库":
            params.update(doc.get("params") or {})
    return params


def canonical_terms() -> list[str]:
    terms: list[str] = []
    for doc in _iter_docs():
        for t in doc.get("terms") or []:
            if t not in terms:
                terms.append(t)
    return terms
