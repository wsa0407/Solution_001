from __future__ import annotations

from typing import Any

from solution_gen.chat.outline_edit import apply_outline_instruction
from solution_gen.domain import JobStatus, PendingConfirm
from solution_gen.pipeline.machine import TransitionError
from solution_gen.service import JobService
from solution_gen.store import save_job
from solution_gen.tools.result import fail, snapshot

_svc = JobService()


def edit_outline(job_id: str, text: str) -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is JobStatus.GENERATING:
        return fail("正文生成中不能改目录。", job)
    if job.status is not JobStatus.OUTLINE_CONFIRM:
        return fail("仅大纲确认门可改章节树。", job)
    changed = apply_outline_instruction(job.chapters, text)
    if not changed:
        return fail("无法按这句话改目录。请点名某一章并说「拆成两章」，或回复确认后 write-chapters。", job)
    try:
        job = _svc.update_outline(job_id, changed)
    except TransitionError as exc:
        return fail(str(exc), _svc.get(job_id))
    job.pending_confirm = PendingConfirm.OUTLINE
    save_job(job)
    titles = "、".join(f"{i+1}.{c.title}" for i, c in enumerate(job.chapters))
    return snapshot(job, replies=[f"已改目录：{titles}。确认后调用 write-chapters。"], next="wait_confirm_then_write_chapters")
