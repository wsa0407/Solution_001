from __future__ import annotations

from typing import Any

from solution_gen.chat.brief import (
    infer_doc_type,
    is_complete,
    is_greeting,
    merge_from_text,
    missing_fields,
    next_question,
    recap,
)
from solution_gen.domain import DOC_TYPE_LABEL, DocType, JobStatus, PendingConfirm, Profile
from solution_gen.genre import apply_pack
from solution_gen.pipeline.machine import TransitionError
from solution_gen.service import JobService
from solution_gen.store import save_job
from solution_gen.tools.result import fail, snapshot

_svc = JobService()


def _apply_fields(profile: Profile, fields: dict[str, Any]) -> Profile:
    mapping = {
        "project_name": "project_name",
        "place": "place",
        "construction_unit": "construction_unit",
        "industry": "industry",
        "need": "need",
        "compilation_unit": "compilation_unit",
        "funding_source": "funding_source",
    }
    for key, attr in mapping.items():
        val = fields.get(key)
        if isinstance(val, str) and val.strip():
            setattr(profile, attr, val.strip())
    if fields.get("budget") is not None and fields.get("budget") != "":
        profile.budget = float(fields["budget"])
    if fields.get("construction_period") is not None and fields.get("construction_period") != "":
        profile.construction_period = int(fields["construction_period"])
    mods = fields.get("modules")
    if isinstance(mods, str) and mods.strip():
        profile.modules = [p.strip() for p in mods.split(",") if p.strip()]
    elif isinstance(mods, list):
        profile.modules = [str(x).strip() for x in mods if str(x).strip()]
    return profile


def collect_brief(
    *,
    job_id: str | None = None,
    text: str = "",
    doc_type: str | None = None,
    owner: str = "dsh",
    **fields: Any,
) -> dict[str, Any]:
    """Merge operator answers. Never drafts an outline until fields are complete and confirmed."""
    if job_id:
        job = _svc.get(job_id)
    else:
        dtype = DocType.SOLUTION
        if doc_type:
            dtype = DocType(doc_type)
        elif text:
            dtype = infer_doc_type(text) or DocType.SOLUTION
        job = _svc.create(dtype, owner=owner)

    if doc_type:
        job.doc_type = DocType(doc_type)
    elif text:
        inferred = infer_doc_type(text)
        if inferred:
            job.doc_type = inferred

    if job.status is not JobStatus.PROFILE:
        return fail("当前不在需求收集阶段，不能改画像字段。", job)

    if is_greeting(text) and not (job.profile and job.profile.project_name) and not any(fields.values()):
        save_job(job)
        return snapshot(job, replies=["请用一句话说需求，例如：帮我写一份青岛的项目建议书。"], next="ask_need")

    current = job.profile or Profile()
    if text:
        miss = missing_fields(current)
        expecting = miss[0] if miss else None
        current = merge_from_text(current, text, expecting=expecting)
    current = _apply_fields(current, fields)
    job.profile = current

    if is_complete(job.profile):
        job.profile = apply_pack(job.profile)
        job.brief_complete = True
        job.pending_confirm = PendingConfirm.BRIEF
        save_job(job)
        recap_text = recap(job.profile, job)
        return snapshot(
            job,
            replies=[recap_text],
            next="wait_confirm_then_draft_outline",
            missing=[],
        )

    job.pending_confirm = None
    job.brief_complete = False
    save_job(job)
    question = next_question(job.profile) or "请再补充一项关键信息。"
    return snapshot(
        job,
        replies=[question],
        next="ask_missing_field",
        missing=missing_fields(job.profile),
    )


async def draft_outline(job_id: str) -> dict[str, Any]:
    """Only after PROFILE fields are complete. Calls submit_profile; model cannot skip the gate."""
    job = _svc.get(job_id)
    if not job.profile or not is_complete(job.profile):
        miss = missing_fields(job.profile or Profile())
        return fail("字段未齐，禁止出目录。先用 collect-brief 补齐。", job, missing=miss, next="collect_brief")
    if not job.brief_complete:
        return fail("操作者尚未确认需求摘要，禁止出目录。", job, next="wait_confirm")
    try:
        job.pending_confirm = None
        job = await _svc.submit_profile(job.id, job.profile)
    except TransitionError as exc:
        return fail(str(exc), _svc.get(job_id))
    job.pending_confirm = PendingConfirm.OUTLINE
    save_job(job)
    titles = "、".join(f"{i+1}.{c.title}" for i, c in enumerate(job.chapters))
    label = DOC_TYPE_LABEL.get(job.doc_type, "方案")
    return snapshot(
        job,
        replies=[
            f"{label}目录草案：{titles}。请操作者确认后调用 write-chapters；改目录用 edit-outline。",
        ],
        next="wait_confirm_then_write_chapters",
    )


def create_job(doc_type: str = "solution", owner: str = "dsh") -> dict[str, Any]:
    job = _svc.create(DocType(doc_type), owner=owner)
    return snapshot(job, replies=[f"已开任务 {job.id}，文档类型 {DOC_TYPE_LABEL.get(job.doc_type, job.doc_type)}。"], next="collect_brief")


def job_status(job_id: str) -> dict[str, Any]:
    return snapshot(_svc.get(job_id), next="continue")
