"""章节序号与大纲对齐。写手常自编「第X章 / X.1」，与 Word 一级标题冲突。"""

from __future__ import annotations

import re

from solution_gen.domain import Chapter, Job

_CN_DIGITS = "零一二三四五六七八九"
_CN_MAP = {ch: i for i, ch in enumerate(_CN_DIGITS)}
_CN_MAP["十"] = 10

_CHAPTER_TOKEN = re.compile(r"^第(?P<n>[一二三四五六七八九十百零]+|\d+)章(?:\s*(?P<title>.*))?$")
_ARABIC_CHAPTER = re.compile(r"^(?:第)?(?P<n>\d+)\s*章(?:\s*(?P<title>.*))?$")
_NUM_TITLE = re.compile(r"^(?P<n>\d+)\s+(?P<title>.+)$")
_SUBHEAD = re.compile(
    r"^(?P<pre>#{1,6}\s*)?(?P<ch>[1-9]|1[0-5])(?P<rest>(?:\.\d+)+)(?P<sp>\s+)(?P<title>\S.*)$"
)
_FIG = re.compile(r"(图|表)\s*([1-9]|1[0-5])([-－])(\d+)")
_UNITISH = re.compile(
    r"(万元|亿元|元|％|%|个月|米|平方米|吨|套|个|项|人|次|小时|km|MHz|ms|V2\.|白皮书)"
)


def chinese_chapter_num(n: int) -> str:
    if n <= 0:
        return str(n)
    if n < 10:
        return _CN_DIGITS[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + _CN_DIGITS[n - 10]
    if n < 100:
        tens, ones = divmod(n, 10)
        head = _CN_DIGITS[tens] + "十"
        return head if ones == 0 else head + _CN_DIGITS[ones]
    return str(n)


def parse_chinese_int(token: str) -> int | None:
    raw = (token or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw == "十":
        return 10
    if raw.startswith("十") and "十" not in raw[1:]:
        rest = raw[1:]
        return 10 + _CN_MAP[rest] if rest in _CN_MAP else None
    if "十" in raw:
        left, right = raw.split("十", 1)
        tens = _CN_MAP.get(left)
        if tens is None:
            return None
        ones = 0 if not right else _CN_MAP.get(right)
        if ones is None:
            return None
        return tens * 10 + ones
    return _CN_MAP.get(raw)


def chapter_index(job: Job, chapter: Chapter) -> int:
    for i, item in enumerate(job.chapters, 1):
        if item.id == chapter.id:
            return i
    return 1


def numbering_prompt(job: Job, chapter: Chapter) -> str:
    index = chapter_index(job, chapter)
    total = len(job.chapters) or 1
    cn = chinese_chapter_num(index)
    catalog = "\n".join(f"{i}. {c.title}" for i, c in enumerate(job.chapters, 1))
    if not catalog:
        catalog = f"{index}. {chapter.title}"
    return (
        f"本章在目录中的位置: 第{cn}章（序号 {index} / 共 {total} 章），标题「{chapter.title}」。\n"
        f"全文目录:\n{catalog}\n"
        f"排版会自动生成一级标题「{index}. {chapter.title}」。"
        f"正文不要再写「第{cn}章 {chapter.title}」「第{index}章」或「# {index} {chapter.title}」这类重复章标题。\n"
        f"小节标题必须用 {index}.1、{index}.2、{index}.1.1；图表用「图{index}-1」「表{index}-1」。"
        f"禁止把本章写成其他章号（例如非第1章却写「第一章」或「1.1」）。\n"
    )


def normalize_chapter_numbering(text: str, index: int, title: str) -> str:
    if not (text or "").strip() or index <= 0:
        return text
    lines = text.replace("\r\n", "\n").split("\n")
    lines = _strip_leading_chapter_heads(lines, index, title)
    out: list[str] = []
    for line in lines:
        out.append(_rewrite_line(line, index))
    return "\n".join(out)


def align_job_numbering(job: Job) -> Job:
    for i, ch in enumerate(job.chapters, 1):
        if ch.content:
            ch.content = normalize_chapter_numbering(ch.content, i, ch.title)
    return job


def numbering_issues(text: str, index: int, title: str, chapter_id: str) -> list[tuple[str, str]]:
    """Return (code, detail) for leftover wrong chapter / subsection numbers."""
    found: list[tuple[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        plain = _plain_heading(line)
        token = _CHAPTER_TOKEN.match(plain) or _ARABIC_CHAPTER.match(plain)
        if token:
            parsed = parse_chinese_int(token.group("n"))
            rest = (token.group("title") or "").strip(" ：:.-")
            if parsed is not None and parsed != index and (not rest or rest == title):
                found.append(
                    (
                        "CH-NUM-01",
                        f"章节「{title}」正文仍用「第{token.group('n')}章」，目录序号是第{index}章。",
                    )
                )
                break
        m = _SUBHEAD.match(line)
        if not m:
            continue
        ch_no = int(m.group("ch"))
        if ch_no != index and _looks_like_heading(m.group("title"), bool(m.group("pre"))):
            found.append(
                (
                    "CH-NUM-02",
                    f"章节「{title}」小节编号写成 {m.group('ch')}{m.group('rest')}，应为 {index}{m.group('rest')}。",
                )
            )
            break
    return found


def _plain_heading(line: str) -> str:
    return re.sub(r"^#{1,6}\s*", "", line.strip()).strip()


def _strip_leading_chapter_heads(lines: list[str], index: int, title: str) -> list[str]:
    i = 0
    dropped = 0
    while i < len(lines) and dropped < 3:
        if not lines[i].strip():
            i += 1
            continue
        if _is_duplicate_chapter_heading(lines[i], title):
            i += 1
            dropped += 1
            continue
        break
    return lines[i:]


def _is_duplicate_chapter_heading(line: str, title: str) -> bool:
    plain = _plain_heading(line)
    if not plain:
        return False
    if plain == title:
        return True
    token = _CHAPTER_TOKEN.match(plain) or _ARABIC_CHAPTER.match(plain)
    if token:
        rest = (token.group("title") or "").strip(" ：:.-")
        return (not rest) or rest == title or title.startswith(rest) or rest.startswith(title)
    numbered = _NUM_TITLE.match(plain)
    if numbered:
        rest = numbered.group("title").strip(" ：:.-")
        return rest == title
    return False


def _rewrite_line(line: str, index: int) -> str:
    m = _SUBHEAD.match(line)
    if m and int(m.group("ch")) != index and _looks_like_heading(m.group("title"), bool(m.group("pre"))):
        line = f"{m.group('pre') or ''}{index}{m.group('rest')}{m.group('sp')}{m.group('title')}"
    return _FIG.sub(lambda mm: f"{mm.group(1)}{index}{mm.group(3)}{mm.group(4)}", line)


def _looks_like_heading(title: str, has_hash: bool) -> bool:
    if has_hash:
        return True
    if _UNITISH.search(title):
        return False
    if len(title) > 40:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", title))
