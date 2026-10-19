from __future__ import annotations

import asyncio

from solution_gen.chat.intent import Intent, classify
from solution_gen.chat.service import handle_chat
from solution_gen.domain import JobStatus, PendingConfirm, Profile
from solution_gen.service import JobService
from solution_gen.store import save_job


def _svc() -> JobService:
    return JobService()


def test_spoken_yes_counts_as_confirm_when_pending() -> None:
    assert classify("对的", JobStatus.PROFILE, PendingConfirm.BRIEF) is Intent.CONFIRM
    assert classify("目录呢", JobStatus.PROFILE, PendingConfirm.BRIEF) is Intent.CONFIRM
    assert classify("你好", JobStatus.PROFILE, None) is Intent.OTHER


def test_confirm_before_brief_complete_does_not_make_outline() -> None:
    svc = _svc()
    job = svc.create()
    result = asyncio.run(handle_chat(svc, job.id, "确认"))
    job = result["job"]
    assert job.status is JobStatus.PROFILE
    assert job.chapters == []
    assert result["pending_confirm"] is None


def test_outline_confirm_starts_generation() -> None:
    svc = _svc()
    job = svc.create()
    profile = Profile(
        place="乐山市",
        industry="低空经济",
        project_name="乐山市低空经济基础设施建设项目",
        construction_unit="乐山低空科技有限公司",
        budget=50000,
        construction_period=24,
        need="示范",
    )
    job = asyncio.run(svc.submit_profile(job.id, profile))
    job.pending_confirm = PendingConfirm.OUTLINE
    save_job(job)
    result = asyncio.run(handle_chat(svc, job.id, "确认"))
    assert result["job"].status is JobStatus.GENERATING
    assert result["start_generation"] is True


def test_confirm_ignored_while_generating() -> None:
    svc = _svc()
    job = svc.create()
    job.status = JobStatus.GENERATING
    save_job(job)
    result = asyncio.run(handle_chat(svc, job.id, "确认"))
    assert result["job"].status is JobStatus.GENERATING
    assert "不会生效" in result["replies"][0]["text"]


def test_skip_qa_rejected_in_chat() -> None:
    svc = _svc()
    job = svc.create()
    job.status = JobStatus.QA_BLOCKED
    save_job(job)
    result = asyncio.run(handle_chat(svc, job.id, "跳过质检"))
    assert result["job"].status is JobStatus.QA_BLOCKED
    assert "不能跳过" in result["replies"][0]["text"]


def test_collect_then_confirm_brief_makes_outline() -> None:
    svc = _svc()
    job = svc.create()
    asyncio.run(handle_chat(svc, job.id, "帮我写一份项目建议书"))
    asyncio.run(handle_chat(svc, job.id, "乐山市低空经济基础设施建设项目"))
    asyncio.run(handle_chat(svc, job.id, "乐山市"))
    asyncio.run(handle_chat(svc, job.id, "乐山低空科技有限公司"))
    asyncio.run(handle_chat(svc, job.id, "50000万，24个月"))
    job = svc.get(job.id)
    if not job.brief_complete:
        asyncio.run(handle_chat(svc, job.id, "项目名称乐山市低空经济基础设施建设项目，属地乐山市，建设单位乐山低空科技有限公司，总投资50000万元，周期24个月"))
    job = svc.get(job.id)
    assert job.pending_confirm is PendingConfirm.BRIEF
    result = asyncio.run(handle_chat(svc, job.id, "确认"))
    assert result["job"].status is JobStatus.OUTLINE_CONFIRM
    assert result["job"].chapters


def test_split_chapter_stays_in_outline_confirm() -> None:
    svc = _svc()
    job = svc.create()
    profile = Profile(
        place="乐山市",
        industry="低空经济",
        project_name="乐山市低空经济基础设施建设项目",
        construction_unit="乐山低空科技有限公司",
        budget=50000,
        construction_period=24,
        need="示范",
    )
    job = asyncio.run(svc.submit_profile(job.id, profile))
    before = len(job.chapters)
    result = asyncio.run(handle_chat(svc, job.id, "把实施计划拆成两章"))
    job = result["job"]
    assert job.status is JobStatus.OUTLINE_CONFIRM
    assert len(job.chapters) == before + 1
    assert any("实施计划（上）" in c.title for c in job.chapters)
