from __future__ import annotations

from typing import Any

from solution_gen.domain import DOC_TYPE_LABEL, Job, PendingConfirm
from solution_gen.labels import STAGE_LABEL

_PENDING_HINT = {
    PendingConfirm.BRIEF: "请回复确认 · 开始做目录",
    PendingConfirm.OUTLINE: "请回复确认 · 开始写正文",
    PendingConfirm.FINAL: "请回复确认 · 交付终稿",
}


def job_title(job: Job) -> str:
    place = (job.profile.place if job.profile else "") or "未定属地"
    dtype = DOC_TYPE_LABEL.get(job.doc_type, "方案")
    stage = STAGE_LABEL.get(job.status, str(job.status))
    return f"{place} · {dtype} · {stage}"


def job_payload(job: Job) -> dict[str, Any]:
    data = job.model_dump(mode="json") if hasattr(job, "model_dump") else job.dict()
    data["stage"] = STAGE_LABEL.get(job.status, str(job.status))
    data["hint"] = _PENDING_HINT.get(job.pending_confirm) or data["stage"]
    data["title"] = job_title(job)
    data["pending_confirm"] = job.pending_confirm.value if job.pending_confirm else None
    return data
