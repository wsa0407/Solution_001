"""确定性状态机。所有合法边写死在 TRANSITIONS，AI 不能改图。"""

from __future__ import annotations

from solution_gen.domain import ENABLED_DOC_TYPES, DocType, Event, Job, JobStatus

TRANSITIONS: dict[JobStatus, dict[Event, JobStatus]] = {
    JobStatus.PROFILE: {Event.SUBMIT_PROFILE: JobStatus.OUTLINE_DRAFT},
    JobStatus.OUTLINE_DRAFT: {Event.OUTLINE_READY: JobStatus.OUTLINE_CONFIRM},
    JobStatus.OUTLINE_CONFIRM: {Event.CONFIRM_OUTLINE: JobStatus.GENERATING},
    JobStatus.GENERATING: {
        Event.CHAPTERS_DONE: JobStatus.DIAGRAM_ASK,
        Event.RESUME_QA: JobStatus.QA_RUNNING,
    },
    JobStatus.DIAGRAM_ASK: {
        Event.SKIP_DIAGRAMS: JobStatus.QA_RUNNING,
        Event.DIAGRAM_SPEC_DONE: JobStatus.DIAGRAM_RUNNING,
    },
    JobStatus.DIAGRAM_RUNNING: {
        Event.DIAGRAMS_DONE: JobStatus.QA_RUNNING,
        Event.DIAGRAM_FAIL: JobStatus.DIAGRAM_ASK,
    },
    JobStatus.QA_RUNNING: {
        Event.QA_PASS: JobStatus.ASSEMBLING,
        Event.QA_FAIL: JobStatus.QA_BLOCKED,
    },
    JobStatus.QA_BLOCKED: {
        Event.REWRITE_CHAPTER: JobStatus.GENERATING,
        Event.SWAP_MATERIAL: JobStatus.GENERATING,
    },
    JobStatus.ASSEMBLING: {Event.ASSEMBLED: JobStatus.FINAL_CONFIRM},
    JobStatus.FINAL_CONFIRM: {
        Event.REVISE: JobStatus.REVISING,
        Event.DELIVER: JobStatus.DELIVERED,
        Event.QA_FAIL: JobStatus.QA_BLOCKED,
    },
    JobStatus.REVISING: {Event.REVISED: JobStatus.QA_RUNNING},
}

BLOCKING_STATUSES = frozenset({
    JobStatus.PROFILE,
    JobStatus.OUTLINE_CONFIRM,
    JobStatus.DIAGRAM_ASK,
    JobStatus.FINAL_CONFIRM,
    JobStatus.QA_BLOCKED,
})
FORBIDDEN_EVENTS = frozenset({Event.SKIP_QA})


class TransitionError(ValueError):
    pass


def apply(job: Job, event: Event) -> Job:
    if event in FORBIDDEN_EVENTS:
        raise TransitionError("质检失败不允许跳过。只能改写问题章或更换素材后重跑。")
    if job.doc_type not in ENABLED_DOC_TYPES:
        raise TransitionError(f"一期未启用文档类型: {job.doc_type}")
    allowed = TRANSITIONS.get(job.status, {})
    nxt = allowed.get(event)
    if nxt is None:
        raise TransitionError(f"非法流转: {job.status} + {event}")
    job.status = nxt
    return job


def can(job: Job, event: Event) -> bool:
    if event in FORBIDDEN_EVENTS:
        return False
    return event in TRANSITIONS.get(job.status, {})
