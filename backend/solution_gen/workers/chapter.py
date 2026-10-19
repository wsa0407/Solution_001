"""章节生成：代码调度 + 依赖波次。不走模型编排。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from solution_gen.config import settings
from solution_gen.domain import Chapter, Job
from solution_gen.genre import closer_sentence, writing_for
from solution_gen.locale_search import fill_locale_search, locale_prompt_block
from solution_gen.memory.warm import upsert_datum, upsert_term
from solution_gen.workers.numbering import chapter_index, normalize_chapter_numbering, numbering_prompt
from solution_gen.workers.prose import is_exportable_body

ProgressCb = Callable[[Job], None]


def chapter_token_estimate(chapter: Chapter) -> int:
    return 800 + chapter.words // 12


def build_chapter_prompt(job: Job, chapter: Chapter) -> str:
    profile = job.profile
    assert profile is not None
    cites = "\n".join(f"- [{c.library}] {c.title}: {c.excerpt}" for c in job.citations[:8])
    guide = writing_for(chapter)
    closer = closer_sentence(profile)
    budget = f"{profile.budget:g} 万元" if profile.budget is not None else "（画像未给）"
    period = f"{profile.construction_period} 个月" if profile.construction_period is not None else "（画像未给）"
    funding = profile.funding_source or "（画像未给）"
    return (
        f"你是固定资产投资类文档的章节写手。只写本章，不要改大纲，不要调度其他章。\n"
        f"文档类型: {job.doc_type}\n"
        f"属地: {profile.place}\n"
        f"行业: {profile.industry}\n"
        f"{numbering_prompt(job, chapter)}"
        f"章标题: {chapter.title}\n"
        f"目标字数: {chapter.words}\n"
        f"是否出图: {'是，文中插入 [DIAGRAM] 占位符，只描述结构化图表数据，不要输出 HTML' if chapter.diagram else '否'}\n"
        f"文类写法: {guide or '按本章标题与要点写，不要用信息化四层架构代替建设模块。'}\n"
        f"写作要点: {chapter.brief}\n"
        f"建设内容收口: {closer}\n"
        f"总投资: {budget}；资金来源: {funding}；建设周期: {period}\n"
        f"编制单位: {profile.compilation_unit or '（未给）'}\n"
        f"术语登记簿: {', '.join(job.warm.terms) or '（空）'}\n"
        f"关键数据登记簿: {', '.join(job.warm.data) or '（空）'}\n"
        f"三库摘录:\n{cites}\n"
        f"{locale_prompt_block(job, chapter)}"
        f"需求要点: {profile.need}\n"
        f"必须使用登记簿术语；投资/周期/收口与画像一致；概述与结论必须点名属地。\n"
        f"产品参数以产品库为准，不要编造指标。\n"
        f"只输出本章中文正文。不要输出思考过程、工具调用、JSON、HTML、代码围栏或会话对象。\n"
    )


async def generate_chapters(job: Job, writer, on_progress: ProgressCb | None = None) -> Job:
    fill_locale_search(job)
    sem = asyncio.Semaphore(settings.chapter_concurrency)

    async def run_one(ch: Chapter) -> None:
        async with sem:
            last_err: Exception | None = None
            for attempt in range(2):
                ch.status = "retry" if attempt else "run"
                if on_progress:
                    on_progress(job)
                try:
                    text = await writer(build_chapter_prompt(job, ch), ch)
                    if not is_exportable_body(text):
                        raise ValueError("写手未返回章节正文")
                    ch.content = normalize_chapter_numbering(text, chapter_index(job, ch), ch.title)
                    ch.status = "done"
                    ch.tokens = max(ch.tokens, 400 + chapter_token_estimate(ch))
                    job.total_tokens = sum(c.tokens for c in job.chapters)
                    if job.profile:
                        upsert_term(job, job.profile.industry)
                        upsert_datum(job, f"{ch.title} 已生成")
                    if on_progress:
                        on_progress(job)
                    return
                except Exception as exc:
                    last_err = exc
                    ch.status = "fail"
            if last_err:
                ch.content = ch.content or f"（生成失败，已重试）{last_err}"
                ch.status = "done"

    pending = [c for c in job.chapters if c.status != "done"]
    done_ids = {c.id for c in job.chapters if c.status == "done"}
    while pending:
        ready = [c for c in pending if all(d in done_ids for d in (c.depends_on or []))]
        if not ready:
            ready = pending[:1]
        await asyncio.gather(*(run_one(c) for c in ready))
        done_ids = {c.id for c in job.chapters if c.status == "done"}
        pending = [c for c in job.chapters if c.status != "done"]
    return job
