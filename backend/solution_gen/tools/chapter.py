from __future__ import annotations

from typing import Any

from solution_gen.domain import JobStatus
from solution_gen.pipeline.machine import TransitionError
from solution_gen.service import JobService
from solution_gen.tools.result import fail, snapshot

_svc = JobService()


async def write_chapters(job_id: str) -> dict[str, Any]:
    """Confirm outline then generate. Fails unless the job is at OUTLINE_CONFIRM."""
    job = _svc.get(job_id)
    if job.status is JobStatus.GENERATING:
        return fail("正在写正文，不能再改目录或重复开写。", job)
    if job.status is not JobStatus.OUTLINE_CONFIRM:
        return fail("未确认目录，不能写正文。", job, next="draft_outline_or_wait_confirm")
    try:
        job = _svc.confirm_outline(job_id)
        job = await _svc.run_generation(job_id)
    except TransitionError as exc:
        return fail(str(exc), _svc.get(job_id))
    return snapshot(
        job,
        replies=["各章正文已写完。文类默认出总体框架图和实施甘特图；流程图按需。也可以 skip-diagrams。"],
        next="emit_diagrams_or_skip",
    )
