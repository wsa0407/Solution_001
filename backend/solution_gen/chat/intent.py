from __future__ import annotations

from enum import StrEnum

from solution_gen.domain import DiagramKind, JobStatus, PendingConfirm


class Intent(StrEnum):
    CONFIRM = "confirm"
    SKIP_QA = "skip_qa"
    SKIP_DIAGRAMS = "skip_diagrams"
    NEW_JOB = "new_job"
    WANT_DIAGRAM = "want_diagram"
    OTHER = "other"


_CONFIRM_EXACT = {
    "确认",
    "确认。",
    "确认！",
    "确认下",
    "确认一下",
    "对的",
    "对",
    "好的",
    "好",
    "是的",
    "没错",
    "可以",
    "行",
    "开始",
    "开始做目录",
    "做目录",
    "出目录",
    "生成目录",
    "目录呢",
}
_SKIP_DIAGRAM = ("都不要", "不需要图", "不用图", "不要图", "先不要图")


def classify(text: str, status: JobStatus, pending: PendingConfirm | None) -> Intent:
    t = (text or "").strip()
    if t in {"跳过", "跳过质检"} or ("跳过" in t and "质检" in t):
        return Intent.SKIP_QA
    if "新开一份" in t or t in {"新开", "重来"}:
        return Intent.NEW_JOB
    if any(k in t for k in _SKIP_DIAGRAM) and status is JobStatus.DIAGRAM_ASK:
        return Intent.SKIP_DIAGRAMS
    if pending and t in _CONFIRM_EXACT:
        return Intent.CONFIRM
    if status is JobStatus.DIAGRAM_ASK and t in _CONFIRM_EXACT:
        return Intent.CONFIRM
    if status is JobStatus.DIAGRAM_ASK and any(k in t for k in ("架构图", "流程图", "甘特图", "甘特")):
        return Intent.WANT_DIAGRAM
    return Intent.OTHER


def diagram_kinds_in(text: str) -> list[DiagramKind]:
    found: list[DiagramKind] = []
    if "架构" in text:
        found.append(DiagramKind.ARCHITECTURE)
    if "流程" in text:
        found.append(DiagramKind.FLOWCHART)
    if "甘特" in text:
        found.append(DiagramKind.GANTT)
    return found
