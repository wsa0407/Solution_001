from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class DocType(StrEnum):
    SOLUTION = "solution"
    FEASIBILITY = "feasibility"
    INITIATION = "initiation"


ENABLED_DOC_TYPES = frozenset({DocType.SOLUTION, DocType.FEASIBILITY, DocType.INITIATION})

DOC_TYPE_LABEL = {
    DocType.SOLUTION: "项目建议书",
    DocType.FEASIBILITY: "可研报告",
    DocType.INITIATION: "立项报告",
}


class JobStatus(StrEnum):
    PROFILE = "profile"
    OUTLINE_DRAFT = "outline_draft"
    OUTLINE_CONFIRM = "outline_confirm"
    GENERATING = "generating"
    DIAGRAM_ASK = "diagram_ask"
    DIAGRAM_RUNNING = "diagram_running"
    QA_RUNNING = "qa_running"
    QA_BLOCKED = "qa_blocked"
    ASSEMBLING = "assembling"
    FINAL_CONFIRM = "final_confirm"
    REVISING = "revising"
    DELIVERED = "delivered"


class Event(StrEnum):
    SUBMIT_PROFILE = "submit_profile"
    OUTLINE_READY = "outline_ready"
    CONFIRM_OUTLINE = "confirm_outline"
    CHAPTERS_DONE = "chapters_done"
    SKIP_DIAGRAMS = "skip_diagrams"
    DIAGRAM_SPEC_DONE = "diagram_spec_done"
    DIAGRAMS_DONE = "diagrams_done"
    DIAGRAM_FAIL = "diagram_fail"
    RESUME_QA = "resume_qa"
    QA_PASS = "qa_pass"
    QA_FAIL = "qa_fail"
    REWRITE_CHAPTER = "rewrite_chapter"
    SWAP_MATERIAL = "swap_material"
    SKIP_QA = "skip_qa"
    ASSEMBLED = "assembled"
    REVISE = "revise"
    REVISED = "revised"
    DELIVER = "deliver"


class PendingConfirm(StrEnum):
    BRIEF = "brief"
    OUTLINE = "outline"
    FINAL = "final"


class DiagramKind(StrEnum):
    ARCHITECTURE = "architecture"
    FLOWCHART = "flowchart"
    GANTT = "gantt"


class ChatMessage(BaseModel):
    role: str
    text: str
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DiagramRequest(BaseModel):
    kind: DiagramKind
    chapter_id: str = ""
    placement: str = ""
    reference: str = ""
    spec_text: str = ""
    status: str = "selected"


class Profile(BaseModel):
    place: str = ""
    industry: str = ""
    words: int = Field(default=80_000, ge=20_000, le=200_000)
    need: str = ""
    project_name: str = ""
    construction_unit: str = ""
    budget: float | None = None
    construction_period: int | None = None
    scenes: list[str] = Field(default_factory=list)
    compilation_unit: str = ""
    funding_source: str = ""
    modules: list[str] = Field(default_factory=list)


class Chapter(BaseModel):
    id: str
    title: str
    words: int = 6000
    diagram: bool = False
    brief: str = ""
    status: str = "wait"
    content: str = ""
    tokens: int = 0
    depends_on: list[str] = Field(default_factory=list)
    diagram_json: dict = Field(default_factory=dict)
    writing: str = ""


class QaIssue(BaseModel):
    code: str
    dimension: str
    chapter_id: str
    detail: str


class WarmMemory(BaseModel):
    terms: list[str] = Field(default_factory=list)
    data: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    library: str
    title: str
    why: str
    excerpt: str = ""
    url: str = ""


class Snapshot(BaseModel):
    at: str
    status: str
    note: str = ""


class Job(BaseModel):
    id: str
    doc_type: DocType = DocType.SOLUTION
    status: JobStatus = JobStatus.PROFILE
    owner: str = "demo"
    profile: Profile | None = None
    chapters: list[Chapter] = Field(default_factory=list)
    warm: WarmMemory = Field(default_factory=WarmMemory)
    citations: list[Citation] = Field(default_factory=list)
    qa_issues: list[QaIssue] = Field(default_factory=list)
    qa_retries: int = 0
    polish_log: list[str] = Field(default_factory=list)
    snapshots: list[Snapshot] = Field(default_factory=list)
    total_tokens: int = 0
    cost_yuan: float = 0.0
    export_path: str = ""
    pending_confirm: PendingConfirm | None = None
    brief_complete: bool = False
    diagram_gate_passed: bool = False
    locale_searched: bool = False
    chat_log: list[ChatMessage] = Field(default_factory=list)
    diagram_requests: list[DiagramRequest] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
