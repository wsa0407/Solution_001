from __future__ import annotations

import pytest

from solution_gen.domain import Event, Job, JobStatus
from solution_gen.pipeline.machine import TransitionError, apply, can


def test_happy_path_to_delivered() -> None:
    job = Job(id="j1")
    apply(job, Event.SUBMIT_PROFILE)
    apply(job, Event.OUTLINE_READY)
    apply(job, Event.CONFIRM_OUTLINE)
    apply(job, Event.CHAPTERS_DONE)
    assert job.status is JobStatus.DIAGRAM_ASK
    apply(job, Event.SKIP_DIAGRAMS)
    apply(job, Event.QA_PASS)
    apply(job, Event.ASSEMBLED)
    apply(job, Event.DELIVER)
    assert job.status is JobStatus.DELIVERED


def test_skip_qa_always_forbidden() -> None:
    job = Job(id="j1", status=JobStatus.QA_BLOCKED)
    assert can(job, Event.SKIP_QA) is False
    with pytest.raises(TransitionError, match="不允许跳过"):
        apply(job, Event.SKIP_QA)
    assert job.status is JobStatus.QA_BLOCKED


def test_qa_blocked_only_rewrite_or_swap() -> None:
    job = Job(id="j1", status=JobStatus.QA_BLOCKED)
    assert can(job, Event.REWRITE_CHAPTER)
    assert can(job, Event.SWAP_MATERIAL)
    assert not can(job, Event.QA_PASS)
    apply(job, Event.REWRITE_CHAPTER)
    assert job.status is JobStatus.GENERATING


def test_cannot_edit_during_generation() -> None:
    job = Job(id="j1", status=JobStatus.GENERATING)
    with pytest.raises(TransitionError, match="非法流转"):
        apply(job, Event.CONFIRM_OUTLINE)


def test_revise_must_reenter_qa() -> None:
    job = Job(id="j1", status=JobStatus.FINAL_CONFIRM)
    apply(job, Event.REVISE)
    apply(job, Event.REVISED)
    assert job.status is JobStatus.QA_RUNNING


def test_diagram_spec_then_qa() -> None:
    job = Job(id="j1", status=JobStatus.DIAGRAM_ASK)
    apply(job, Event.DIAGRAM_SPEC_DONE)
    assert job.status is JobStatus.DIAGRAM_RUNNING
    apply(job, Event.DIAGRAMS_DONE)
    assert job.status is JobStatus.QA_RUNNING


def test_resume_qa_after_diagram_gate() -> None:
    job = Job(id="j1", status=JobStatus.GENERATING)
    apply(job, Event.RESUME_QA)
    assert job.status is JobStatus.QA_RUNNING


def test_diagram_fail_returns_to_ask() -> None:
    job = Job(id="j1", status=JobStatus.DIAGRAM_RUNNING)
    apply(job, Event.DIAGRAM_FAIL)
    assert job.status is JobStatus.DIAGRAM_ASK


def test_feasibility_enabled() -> None:
    from solution_gen.domain import DocType

    job = Job(id="j1", doc_type=DocType.FEASIBILITY)
    apply(job, Event.SUBMIT_PROFILE)
    assert job.status is JobStatus.OUTLINE_DRAFT
