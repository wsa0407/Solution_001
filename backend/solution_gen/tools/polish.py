from __future__ import annotations

from solution_gen.domain import Job, JobStatus
from solution_gen.pipeline.machine import TransitionError
from solution_gen.service import JobService
from solution_gen.tools.result import fail, snapshot

_svc = JobService()

_FORBIDDEN_OPS = frozenset({"skip-qa", "skip_qa", "skipqa", "skip"})


async def polish_deliver(
    job_id: str,
    op: str = "run-qa",
    chapter_id: str = "",
    instruction: str = "",
    material_title: str = "",
) -> dict[str, Any]:
    """QA then Word. Failures can only rewrite or swap material. There is no skip-qa."""
    key = (op or "").strip().lower().replace("_", "-")
    if key in _FORBIDDEN_OPS:
        job = _svc.get(job_id)
        return fail("质检不能跳过。只能 rewrite 问题章或 swap-material。", job)

    job = _svc.get(job_id)

    if key in {"run-qa", "qa", ""}:
        if job.status is JobStatus.QA_RUNNING:
            try:
                job = await _svc.run_qa(job_id)
            except TransitionError as exc:
                return fail(str(exc), _svc.get(job_id))
            return _after_qa(job)
        if job.status is JobStatus.QA_BLOCKED:
            return snapshot(
                job,
                replies=["质检未通过。只能 rewrite-chapter 或 swap-material，没有 skip-qa。"],
                next="rewrite_or_swap",
            )
        if job.status is JobStatus.FINAL_CONFIRM:
            return snapshot(job, replies=["质检已通过，Word 已组装。操作者确认后 deliver。"], next="wait_confirm_then_deliver")
        if job.status is JobStatus.DELIVERED:
            return snapshot(job, replies=["已经交付。"], next="done")
        return fail("当前还不能质检或交付。", job)

    if key in {"rewrite", "rewrite-chapter"}:
        if job.status is not JobStatus.QA_BLOCKED:
            return fail("仅质检失败后可改写问题章。", job)
        if not chapter_id:
            chapter_id = job.qa_issues[0].chapter_id if job.qa_issues else (job.chapters[0].id if job.chapters else "")
        try:
            job = _svc.rewrite(job_id, chapter_id, instruction or "按质检意见改写")
            job = await _svc.run_generation(job_id)
        except TransitionError as exc:
            return fail(str(exc), _svc.get(job_id))
        return snapshot(job, replies=["已改写并重跑。"], next="continue")

    if key in {"swap", "swap-material"}:
        if job.status is not JobStatus.QA_BLOCKED:
            return fail("仅质检失败后可换素材。", job)
        if not chapter_id:
            chapter_id = job.qa_issues[0].chapter_id if job.qa_issues else (job.chapters[0].id if job.chapters else "")
        try:
            job = _svc.swap_material(job_id, chapter_id, material_title or instruction or "产品库条目")
            job = await _svc.run_generation(job_id)
        except TransitionError as exc:
            return fail(str(exc), _svc.get(job_id))
        return snapshot(job, replies=["已换素材并重跑。"], next="continue")

    if key == "revise":
        if job.status is not JobStatus.FINAL_CONFIRM:
            return fail("仅终稿确认门可按操作者意见修订（修订后必须再质检）。", job)
        try:
            job = _svc.revise(job_id, instruction or "按意见修订")
            job = await _svc.run_generation(job_id)
        except TransitionError as exc:
            return fail(str(exc), _svc.get(job_id))
        return snapshot(job, replies=["已修订并复检。"], next="continue")

    if key == "deliver":
        if job.status is not JobStatus.FINAL_CONFIRM:
            return fail("未到终稿确认，不能交付。", job)
        if not job.export_path:
            return fail("还没有 Word 路径，不能交付。", job)
        try:
            job = _svc.deliver(job_id)
        except TransitionError as exc:
            return fail(str(exc), job)
        return snapshot(job, replies=[f"终稿已交付：{job.export_path}"], next="done")

    return fail(f"未知 polish 操作: {op}。允许 run-qa / rewrite / swap / revise / deliver。没有 skip-qa。", job)


def _after_qa(job: Job) -> dict:
    if job.status is JobStatus.FINAL_CONFIRM:
        return snapshot(job, replies=["质检通过，Word 已组装。操作者确认后 deliver。"], next="wait_confirm_then_deliver")
    return snapshot(
        job,
        replies=["质检未通过。只能 rewrite 或 swap-material，不能 skip-qa。"],
        next="rewrite_or_swap",
    )
