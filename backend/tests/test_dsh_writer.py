from __future__ import annotations

import asyncio

from solution_gen.config import settings
from solution_gen.domain import Chapter, Job, JobStatus, Profile
from solution_gen.llm import complete
from solution_gen.view import job_title
from solution_gen.workers.runtime import grounded_writer


def test_complete_without_keys_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    text, tokens = asyncio.run(complete("写一章项目概述"))
    assert text is None
    assert tokens == 0


def test_grounded_writer_stubs_without_keys(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    ch = Chapter(id="c1", title="项目概述", words=4000, brief="交代范围。")
    text = asyncio.run(grounded_writer("属地:乐山市\n行业:低空经济", ch, None))
    assert "项目概述" in text
    assert "乐山" in text
    assert "RunResult" not in text
    assert len(text) > 40


def test_job_title_is_readable_not_uuid() -> None:
    job = Job(
        id="ab12cd34",
        status=JobStatus.DIAGRAM_ASK,
        profile=Profile(place="乐山市", industry="低空经济"),
    )
    title = job_title(job)
    assert "乐山市" in title
    assert "项目建议书" in title
    assert "询问配图" in title
    assert job.id not in title
    assert "Token" not in title
    assert "HARNESS" not in title
    assert "Worker" not in title
