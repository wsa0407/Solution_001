from __future__ import annotations

from solution_gen.domain import JobStatus

STAGE_LABEL = {
    JobStatus.PROFILE: "收集确认",
    JobStatus.OUTLINE_DRAFT: "正在起草目录",
    JobStatus.OUTLINE_CONFIRM: "请确认目录",
    JobStatus.GENERATING: "正在写正文",
    JobStatus.DIAGRAM_ASK: "询问配图",
    JobStatus.DIAGRAM_RUNNING: "正在出图",
    JobStatus.QA_RUNNING: "正在核对",
    JobStatus.QA_BLOCKED: "质检未通过",
    JobStatus.ASSEMBLING: "正在组装",
    JobStatus.FINAL_CONFIRM: "请确认终稿",
    JobStatus.REVISING: "正在按你的话修订",
    JobStatus.DELIVERED: "已交付",
}
