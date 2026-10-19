"""规则引擎质检。不经模型自判。文类闭合规则按合同，术语别名按行业包。"""

from __future__ import annotations

import re

from solution_gen.domain import Job, QaIssue
from solution_gen.genre import closer_sentence, required_titles, resolve_pack, selected_modules
from solution_gen.locale_search import needs_locale_policy
from solution_gen.rag import canonical_params
from solution_gen.workers.numbering import numbering_issues

HARD_CHECKS = (
    "term_consistency",
    "param_grounded",
    "locale_filter",
    "chapter_complete",
    "figure_body_align",
    "word_floor",
    "genre_chapters",
    "budget_echo",
    "module_echo",
    "chapter_numbering",
    "locale_policy",
)


def run_qa(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    issues.extend(_term_consistency(job))
    issues.extend(_param_grounded(job))
    issues.extend(_chapter_complete(job))
    issues.extend(_word_floor(job))
    issues.extend(_figure_placeholders(job))
    issues.extend(_locale_mentions(job))
    issues.extend(_genre_chapters(job))
    issues.extend(_budget_echo(job))
    issues.extend(_module_echo(job))
    issues.extend(_chapter_numbering(job))
    issues.extend(_locale_policy(job))
    return issues


def _param_grounded(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    params = canonical_params()
    latency = params.get("边缘节点时延")
    if not latency:
        return issues
    for ch in job.chapters:
        if "50ms" in (ch.content or "") and "20ms" not in ch.content:
            issues.append(
                QaIssue(
                    code="PARAM-11",
                    dimension="产品参数与知识库一致",
                    chapter_id=ch.id,
                    detail=f"边缘节点时延写成 50ms，产品库口径为 {latency}。",
                )
            )
    return issues


def _term_consistency(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    pack = resolve_pack(job.profile) if job.profile else None
    aliases = dict(pack.term_aliases) if pack else {}
    for ch in job.chapters:
        for wrong, canonical in aliases.items():
            if wrong in ch.content and canonical in job.warm.terms:
                issues.append(
                    QaIssue(
                        code="TERM-02",
                        dimension="术语全文一致",
                        chapter_id=ch.id,
                        detail=f"正文使用「{wrong}」，术语登记簿已登记「{canonical}」。",
                    )
                )
    return issues


def _chapter_complete(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    for ch in job.chapters:
        if not (ch.content or "").strip():
            issues.append(
                QaIssue(
                    code="CH-01",
                    dimension="章节完整性",
                    chapter_id=ch.id,
                    detail=f"章节「{ch.title}」正文为空。",
                )
            )
    return issues


def _word_floor(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    for ch in job.chapters:
        n = len(re.findall(r"\S", ch.content or ""))
        floor = max(200, int(ch.words * 0.15))
        if ch.content and n < floor:
            issues.append(
                QaIssue(
                    code="LEN-01",
                    dimension="字数下限",
                    chapter_id=ch.id,
                    detail=f"章节「{ch.title}」有效字数 {n}，低于下限 {floor}。",
                )
            )
    return issues


def _figure_placeholders(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    for ch in job.chapters:
        if ch.diagram and ch.content and "【图" not in ch.content and "[DIAGRAM]" not in ch.content:
            issues.append(
                QaIssue(
                    code="FIG-01",
                    dimension="图文一致",
                    chapter_id=ch.id,
                    detail=f"章节「{ch.title}」要求出图，但正文无图表占位符。",
                )
            )
    return issues


def _locale_targets(job: Job) -> list:
    keyed = [
        c
        for c in job.chapters
        if c.writing in {"overview", "conclusion", "initiation_basis", "request"}
        or any(k in c.title for k in ("概述", "结论"))
    ]
    if keyed:
        return keyed
    if not job.chapters:
        return []
    return [job.chapters[0], job.chapters[-1]]


def _locale_mentions(job: Job) -> list[QaIssue]:
    if not job.profile:
        return []
    place = job.profile.place.rstrip("市县区")
    issues: list[QaIssue] = []
    if not place:
        return issues
    for ch in _locale_targets(job):
        if ch.content and place not in ch.content and job.profile.place not in ch.content:
            issues.append(
                QaIssue(
                    code="LOC-01",
                    dimension="属地素材强制过滤",
                    chapter_id=ch.id,
                    detail=f"概述或结论未出现属地「{job.profile.place}」。",
                )
            )
    return issues


_VAGUE_POLICY = re.compile(r"相关规划|有关政策|有关部门(?:文件)?")


def _has_vague_policy(text: str) -> bool:
    cleaned = re.sub(r"不要写「[^」]*」", "", text or "")
    return bool(_VAGUE_POLICY.search(cleaned))


def _policy_title_mentioned(content: str, title: str) -> bool:
    raw = (title or "").replace("《", "").replace("》", "").strip()
    if not raw:
        return False
    if raw in content:
        return True
    core = re.sub(r"[^\u4e00-\u9fff]", "", raw)
    return len(core) >= 6 and core[:6] in content


def _locale_policy(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    hits = [c for c in job.citations if c.library in {"检索", "地方库"} and c.title]
    for ch in job.chapters:
        if not needs_locale_policy(ch) or not (ch.content or "").strip():
            continue
        text = ch.content
        named = any(_policy_title_mentioned(text, c.title) for c in hits)
        vague = _has_vague_policy(text)
        web_hits = [c for c in hits if c.library == "检索"]
        if vague and not named:
            issues.append(
                QaIssue(
                    code="LOC-02",
                    dimension="地方政策可核验",
                    chapter_id=ch.id,
                    detail=f"章节「{ch.title}」使用空泛「相关规划/有关政策」，未点名属地库或检索摘录中的文件名。",
                )
            )
        elif web_hits and not named:
            issues.append(
                QaIssue(
                    code="LOC-02",
                    dimension="地方政策可核验",
                    chapter_id=ch.id,
                    detail=f"章节「{ch.title}」有地方检索命中，正文须点名其中至少一条标题。",
                )
            )
    return issues


def _genre_chapters(job: Job) -> list[QaIssue]:
    if not job.profile or not job.chapters:
        return []
    titles = " ".join(c.title for c in job.chapters)
    missing = [t for t in required_titles(job.profile, job.doc_type) if t not in titles]
    if not missing:
        return []
    return [
        QaIssue(
            code="GENRE-01",
            dimension="文类必选章",
            chapter_id=job.chapters[0].id,
            detail="缺少文类必选章：" + "、".join(missing),
        )
    ]


def _budget_echo(job: Job) -> list[QaIssue]:
    if not job.profile or job.profile.budget is None:
        return []
    token = f"{job.profile.budget:g}"
    targets = [
        c
        for c in job.chapters
        if c.writing in {"overview", "investment", "economy", "conclusion", "schedule_budget"}
        or any(k in c.title for k in ("概述", "投资", "财务", "经济评价", "结论"))
    ]
    issues: list[QaIssue] = []
    for ch in targets:
        if ch.content and token not in ch.content:
            issues.append(
                QaIssue(
                    code="NUM-01",
                    dimension="投资口径闭合",
                    chapter_id=ch.id,
                    detail=f"章节「{ch.title}」未回写总投资 {token} 万元。",
                )
            )
    return issues


def _chapter_numbering(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    for i, ch in enumerate(job.chapters, 1):
        for code, detail in numbering_issues(ch.content or "", i, ch.title, ch.id):
            issues.append(
                QaIssue(
                    code=code,
                    dimension="章节编号与目录一致",
                    chapter_id=ch.id,
                    detail=detail,
                )
            )
    return issues


def _module_echo(job: Job) -> list[QaIssue]:
    if not job.profile:
        return []
    mods = selected_modules(job.profile)
    if not mods:
        return []
    closer = closer_sentence(job.profile)
    targets = [
        c
        for c in job.chapters
        if c.writing in {"overview", "scheme", "overall", "conclusion"}
        or any(k in c.title for k in ("概述", "建设方案", "总体方案", "结论"))
    ]
    issues: list[QaIssue] = []
    for ch in targets:
        if not ch.content:
            continue
        missing = [m.title for m in mods if m.title not in ch.content]
        if missing:
            issues.append(
                QaIssue(
                    code="MOD-01",
                    dimension="建设模块三处一致",
                    chapter_id=ch.id,
                    detail=f"章节「{ch.title}」未覆盖已选模块：{'、'.join(missing[:6])}。收口句应为「{closer}」。",
                )
            )
    return issues
