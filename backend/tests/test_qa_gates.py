from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from solution_gen.domain import Chapter, JobStatus, Profile
from solution_gen.pipeline.machine import TransitionError
from solution_gen.qa.engine import run_qa
from solution_gen.rag import retrieve
from solution_gen.service import JobService
from solution_gen.store import save_job


def _filled(ch: Chapter, place: str = "乐山市") -> Chapter:
    pad = "建设内容。" * 800
    extra = f"{place}低空智联网。" if ch.id in {"c1", "c10"} or "概述" in ch.title or "结论" in ch.title or "请示" in ch.title else "低空智联网。"
    fig = "【图 1-1】[DIAGRAM]" if ch.diagram else ""
    ch.content = f"{ch.title}。{ch.brief}{extra}{fig}{pad}"
    ch.status = "done"
    return ch


def _ready(svc: JobService, monkeypatch: pytest.MonkeyPatch) -> str:
    job = svc.create()
    asyncio.run(svc.submit_profile(job.id, Profile(place="乐山市", industry="低空经济", words=80000, need="示范")))
    svc.confirm_outline(job.id)
    return job.id


def test_skip_endpoint_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = JobService()
    jid = _ready(svc, monkeypatch)
    job = svc.get(jid)
    job.status = JobStatus.QA_BLOCKED
    save_job(job)
    with pytest.raises(TransitionError, match="不允许跳过"):
        svc.skip_qa(jid)


def test_qa_pass_when_content_grounded(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = JobService()
    jid = _ready(svc, monkeypatch)
    job = svc.get(jid)
    job.chapters = [_filled(c) for c in job.chapters]
    job.status = JobStatus.QA_RUNNING
    save_job(job)
    job = asyncio.run(svc.run_qa(jid))
    assert job.status is JobStatus.FINAL_CONFIRM
    assert job.qa_issues == []
    assert job.export_path and Path(job.export_path).exists()


def test_term_drift_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = JobService()
    jid = _ready(svc, monkeypatch)
    job = svc.get(jid)
    job.chapters = [_filled(c) for c in job.chapters]
    job.chapters[3].content += "采用低空感知网组网。"
    issues = run_qa(job)
    assert any(i.code == "TERM-02" for i in issues)


def test_locale_library_filtered() -> None:
    cites = retrieve(Profile(place="成都市", industry="低空经济", words=20000, need="智联网"), "低空")
    locale = [c for c in cites if c.library == "地方库"]
    assert all("乐山" not in c.title for c in locale)
