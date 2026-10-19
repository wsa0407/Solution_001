from __future__ import annotations

from copy import deepcopy

from solution_gen.domain import Chapter


def apply_outline_instruction(chapters: list[Chapter], text: str) -> list[Chapter] | None:
    """规则改目录。认不出则返回 None。"""
    if "拆" not in text and "分成两" not in text:
        return None
    for i, ch in enumerate(chapters):
        if ch.title and (ch.title in text or ch.title.removeprefix("项目") in text):
            a, b = deepcopy(ch), deepcopy(ch)
            a.title = f"{ch.title}（上）"
            b.title = f"{ch.title}（下）"
            b.id = f"{ch.id}b"
            b.depends_on = [a.id]
            return chapters[:i] + [a, b] + chapters[i + 1 :]
    return None
