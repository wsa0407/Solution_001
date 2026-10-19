from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from solution_gen.domain import JobStatus, Profile
from solution_gen.service import JobService
from solution_gen.store import save_job
from solution_gen.tools.dispatch import ACTIONS, FORBIDDEN_ACTIONS, dispatch


def _profile() -> Profile:
    return Profile(
        place="乐山市",
        industry="低空经济",
        project_name="乐山市低空经济基础设施建设项目",
        construction_unit="乐山低空科技有限公司",
        budget=50000,
        construction_period=24,
        need="示范",
    )


def test_skip_qa_is_not_a_tool() -> None:
    assert "skip-qa" not in ACTIONS
    assert "skip-qa" in FORBIDDEN_ACTIONS
    result = asyncio.run(dispatch("skip-qa", {"job_id": "x"}))
    assert result["ok"] is False
    assert "没有" in result["error"]


def test_write_chapters_before_outline_confirm_fails() -> None:
    created = asyncio.run(dispatch("create-job", {"doc_type": "solution"}))
    jid = created["job_id"]
    result = asyncio.run(dispatch("write-chapters", {"job_id": jid}))
    assert result["ok"] is False
    assert "不能写正文" in result["error"]
    status = asyncio.run(dispatch("status", {"job_id": jid}))
    assert status["status"] == "profile"
    assert status["chapters"] == []


def test_draft_outline_before_brief_complete_fails() -> None:
    created = asyncio.run(dispatch("create-job", {"doc_type": "solution"}))
    jid = created["job_id"]
    collected = asyncio.run(dispatch("collect-brief", {"job_id": jid, "text": "帮我写一份项目建议书"}))
    assert collected["ok"]
    assert collected["status"] == "profile"
    result = asyncio.run(dispatch("draft-outline", {"job_id": jid}))
    assert result["ok"] is False
    assert "禁止出目录" in result["error"]


def test_collect_complete_then_draft_outline() -> None:
    created = asyncio.run(dispatch("create-job", {"doc_type": "solution"}))
    jid = created["job_id"]
    result = asyncio.run(
        dispatch(
            "collect-brief",
            {
                "job_id": jid,
                "project_name": "乐山市低空经济基础设施建设项目",
                "place": "乐山市",
                "construction_unit": "乐山低空科技有限公司",
                "budget": 50000,
                "construction_period": 24,
                "need": "示范",
            },
        )
    )
    assert result["ok"]
    assert result["brief_complete"] is True
    assert result["pending_confirm"] == "brief"
    assert result["status"] == "profile"
    drafted = asyncio.run(dispatch("draft-outline", {"job_id": jid}))
    assert drafted["ok"]
    assert drafted["status"] == "outline_confirm"
    titles = " ".join(c["title"] for c in drafted["chapters"])
    assert "项目建设方案" in titles
    assert "总体架构" not in titles
    assert drafted["genre"]["name"] == "固定资产投资项目建议书"
    assert drafted["genre"]["pack"] == "低空经济"


def test_edit_outline_rejected_while_generating() -> None:
    svc = JobService()
    job = svc.create()
    job.profile = _profile()
    job.brief_complete = True
    save_job(job)
    job = asyncio.run(svc.submit_profile(job.id, job.profile))
    job.status = JobStatus.GENERATING
    job.pending_confirm = None
    save_job(job)
    result = asyncio.run(dispatch("edit-outline", {"job_id": job.id, "text": "把实施计划拆成两章"}))
    assert result["ok"] is False
    assert "不能改目录" in result["error"]


def test_polish_op_cannot_skip_qa() -> None:
    created = asyncio.run(dispatch("create-job", {"doc_type": "solution"}))
    result = asyncio.run(dispatch("polish-deliver", {"job_id": created["job_id"], "op": "skip-qa"}))
    assert result["ok"] is False
    assert "不能跳过" in result["error"] or "没有" in result["error"]


def test_feasibility_reuses_collect_and_draft() -> None:
    created = asyncio.run(dispatch("create-job", {"doc_type": "feasibility"}))
    jid = created["job_id"]
    result = asyncio.run(
        dispatch(
            "collect-brief",
            {
                "job_id": jid,
                "text": "帮我写一份可研",
                "project_name": "青岛市低空经济基础设施建设项目",
                "place": "青岛市",
                "construction_unit": "青岛低空发展中心",
                "budget": 80000,
                "construction_period": 36,
            },
        )
    )
    assert result["ok"]
    assert result["doc_type"] == "feasibility"
    drafted = asyncio.run(dispatch("draft-outline", {"job_id": jid}))
    assert drafted["ok"]
    titles = " ".join(c["title"] for c in drafted["chapters"])
    assert "经济评价" in titles or "多方案比选" in titles


def test_cli_rejects_skip_qa() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "solution_gen.tools", "skip-qa", "--job-id", "x"],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=False,
    )
    data = json.loads(proc.stdout)
    assert data["ok"] is False
    assert proc.returncode != 0


def test_skill_http_has_no_skip_qa() -> None:
    from fastapi.testclient import TestClient

    from solution_gen.gateway.app import app

    client = TestClient(app)
    catalog = client.get("/api/skills").json()
    assert "skip-qa" not in catalog["actions"]
    denied = client.post("/api/skills/skip-qa", json={"job_id": "x"})
    assert denied.status_code == 400
    home = client.get("/api/health")
    assert home.status_code == 200
    assert home.json()["ui"] == "dsh-web"
