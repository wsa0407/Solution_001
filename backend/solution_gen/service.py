from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from solution_gen.assemble import assemble
from solution_gen.config import settings
from solution_gen.domain import (
    ENABLED_DOC_TYPES,
    Chapter,
    ChatMessage,
    Citation,
    DocType,
    Event,
    Job,
    JobStatus,
    PendingConfirm,
    Profile,
    Snapshot,
)
from solution_gen.genre import apply_pack
from solution_gen.memory.warm import seed_warm, upsert_term
from solution_gen.pipeline.machine import TransitionError, apply
from solution_gen.qa.engine import run_qa
from solution_gen.rag import canonical_terms, retrieve
from solution_gen.store import get_job as store_get
from solution_gen.store import list_jobs as store_list
from solution_gen.store import save_job
from solution_gen.workers.chapter import generate_chapters
from solution_gen.workers.outline import default_outline
from solution_gen.workers.runtime import grounded_writer

ChapterWriter = Callable[[str, Chapter], Awaitable[str]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snap(job: Job, note: str) -> None:
    job.snapshots.append(Snapshot(at=_now(), status=str(job.status), note=note))


def _persist(job: Job) -> Job:
    job.cost_yuan = round(job.total_tokens / 1000 * settings.token_price_per_1k, 4)
    return save_job(job)


class JobService:
    def create(self, doc_type: DocType = DocType.SOLUTION, owner: str = "demo") -> Job:
        if doc_type not in ENABLED_DOC_TYPES:
            raise TransitionError(f"未启用文档类型: {doc_type}")
        job = Job(id=str(uuid.uuid4())[:8], doc_type=doc_type, owner=owner)
        _snap(job, "创建任务")
        return _persist(job)

    def get(self, job_id: str) -> Job:
        return store_get(job_id)

    def list(self, owner: str | None = None) -> list[Job]:
        return store_list(owner)

    async def submit_profile(self, job_id: str, profile: Profile) -> Job:
        job = self.get(job_id)
        job.profile = apply_pack(profile)
        job.citations = retrieve(job.profile, job.profile.need or job.profile.industry)
        apply(job, Event.SUBMIT_PROFILE)
        job.chapters = default_outline(job.profile, job.doc_type)
        apply(job, Event.OUTLINE_READY)
        _snap(job, "画像提交，大纲待确认")
        return _persist(job)

    def update_outline(self, job_id: str, chapters: list[Chapter]) -> Job:
        job = self.get(job_id)
        if job.status is not JobStatus.OUTLINE_CONFIRM:
            raise TransitionError("仅大纲确认门可改章节树与要点。")
        if len(chapters) < 3:
            raise TransitionError("大纲至少 3 章。")
        job.chapters = chapters
        return _persist(job)

    def confirm_outline(self, job_id: str) -> Job:
        job = self.get(job_id)
        if not job.profile:
            raise TransitionError("缺少项目画像。")
        job.warm = seed_warm(job.profile)
        for t in canonical_terms():
            upsert_term(job, t)
        for ch in job.chapters:
            ch.status = "wait"
            ch.content = ""
        apply(job, Event.CONFIRM_OUTLINE)
        _snap(job, "大纲确认")
        return _persist(job)

    async def _writer(self, prompt: str, chapter: Chapter) -> str:
        job_id = getattr(self, "_current_job_id", "")
        job = self.get(job_id) if job_id else None
        return await grounded_writer(prompt, chapter, job)

    async def run_generation(self, job_id: str, writer: ChapterWriter | None = None) -> Job:
        job = self.get(job_id)
        if job.status not in {JobStatus.GENERATING, JobStatus.REVISING}:
            raise TransitionError("当前不在分章生成状态。")
        self._current_job_id = job_id

        async def wrapped(prompt: str, chapter: Chapter) -> str:
            if writer:
                return await writer(prompt, chapter)
            return await grounded_writer(prompt, chapter, self.get(job_id))

        job = self.get(job_id)
        await generate_chapters(job, wrapped, on_progress=lambda j: _persist(j))
        job = self.get(job_id)
        if job.status is JobStatus.REVISING:
            apply(job, Event.REVISED)
            _persist(job)
            return await self.run_qa(job_id)
        if job.diagram_gate_passed:
            apply(job, Event.RESUME_QA)
            _persist(job)
            return await self.run_qa(job_id)
        apply(job, Event.CHAPTERS_DONE)
        job.chat_log.append(
            ChatMessage(
                role="assistant",
                text="各章正文已经写完。需要架构图、流程图还是甘特图？也可以回复「都不要」。",
            )
        )
        _persist(job)
        return job

    def skip_diagrams(self, job_id: str) -> Job:
        job = self.get(job_id)
        apply(job, Event.SKIP_DIAGRAMS)
        job.diagram_gate_passed = True
        drawn = [r for r in job.diagram_requests if r.status == "drawn"]
        keep_chapters = {r.chapter_id for r in drawn}
        job.diagram_requests = drawn
        for ch in job.chapters:
            if ch.id not in keep_chapters:
                ch.diagram = False
                ch.diagram_json = {}
        _persist(job)
        return job

    def begin_diagrams(self, job_id: str) -> Job:
        job = self.get(job_id)
        apply(job, Event.DIAGRAM_SPEC_DONE)
        _snap(job, "出图需求确认")
        return _persist(job)

    async def run_diagrams(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status is not JobStatus.DIAGRAM_RUNNING:
            raise TransitionError("当前不在出图状态。")
        # attach-diagram already wrote PNGs for drawn requests. Do not invent
        # color-box SVG for unconfirmed kinds.
        job.diagram_gate_passed = True
        drawn = [r for r in job.diagram_requests if r.status == "drawn"]
        keep_chapters = {r.chapter_id for r in drawn}
        job.diagram_requests = drawn
        for ch in job.chapters:
            if ch.id not in keep_chapters:
                ch.diagram = False
                ch.diagram_json = {}
        apply(job, Event.DIAGRAMS_DONE)
        job.chat_log.append(ChatMessage(role="assistant", text="图已写入文稿，开始按规则核对正文。"))
        _persist(job)
        return await self.run_qa(job_id)

    async def run_qa(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status is not JobStatus.QA_RUNNING:
            raise TransitionError("当前不在质检状态。")
        issues = run_qa(job)
        job.qa_issues = issues
        if not issues:
            job.qa_retries = 0
            apply(job, Event.QA_PASS)
            assemble(job)
            apply(job, Event.ASSEMBLED)
            job.pending_confirm = PendingConfirm.FINAL
            job.chat_log.append(
                ChatMessage(role="assistant", text="质检通过，Word 已组装。回复「确认」交付，终稿路径会在对话里给出。")
            )
            _snap(job, "质检通过并组装")
            return _persist(job)
        hard = [i for i in issues if i.code != "CH-01"]
        if hard:
            apply(job, Event.QA_FAIL)
            return _persist(job)
        job.qa_retries += 1
        if job.qa_retries <= settings.qa_max_retries:
            for issue in issues:
                ch = next((c for c in job.chapters if c.id == issue.chapter_id), None)
                if ch:
                    ch.status = "retry"
                    ch.content = ""
            apply(job, Event.QA_FAIL)
            apply(job, Event.REWRITE_CHAPTER)
            _persist(job)
            return await self.run_generation(job_id)
        apply(job, Event.QA_FAIL)
        return _persist(job)

    def rewrite(self, job_id: str, chapter_id: str, instruction: str) -> Job:
        job = self.get(job_id)
        ch = next((c for c in job.chapters if c.id == chapter_id), None)
        if not ch:
            raise TransitionError("未知章节。")
        ch.brief = f"{ch.brief}\n修订指令: {instruction}"
        ch.status = "wait"
        ch.content = ""
        job.qa_retries = 0
        apply(job, Event.REWRITE_CHAPTER)
        return _persist(job)

    def swap_material(self, job_id: str, chapter_id: str, material_title: str) -> Job:
        job = self.get(job_id)
        extra = next((c for c in job.citations if c.title == material_title), None)
        if extra is None:
            job.citations.append(Citation(library="产品库", title=material_title, why="人工换素材", excerpt=material_title))
            _persist(job)
        return self.rewrite(job_id, chapter_id, f"换用素材: {material_title}")

    def skip_qa(self, job_id: str) -> Job:
        job = self.get(job_id)
        apply(job, Event.SKIP_QA)
        return job

    def revise(self, job_id: str, instruction: str) -> Job:
        job = self.get(job_id)
        apply(job, Event.REVISE)
        job.polish_log.append(instruction)
        targets = [c for c in job.chapters if c.title in instruction] or job.chapters
        for ch in targets:
            ch.brief = f"{ch.brief}\n修订指令: {instruction}"
            ch.status = "wait"
            ch.content = ""
        return _persist(job)

    def deliver(self, job_id: str) -> Job:
        job = self.get(job_id)
        apply(job, Event.DELIVER)
        _snap(job, "确认交付")
        return _persist(job)
