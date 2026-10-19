from __future__ import annotations

from fastapi.testclient import TestClient

from solution_gen.gateway.app import app
from solution_gen.tools.dispatch import ACTIONS, FORBIDDEN_ACTIONS

client = TestClient(app)


def test_python_agent_loop_http_is_gone() -> None:
    assert client.post("/api/agent/session").status_code == 404
    assert client.post("/api/agent/turn", json={"text": "帮我写一份项目建议书"}).status_code == 404


def test_health_ui_is_dsh_web() -> None:
    home = client.get("/api/health")
    assert home.status_code == 200
    body = home.json()
    assert body["status"] == "ok"
    assert body["role"] == "skill-backend"
    assert body["ui"] == "dsh-web"


def test_jobs_desk_endpoints() -> None:
    listed = client.get("/api/jobs")
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)


def test_skill_backend_has_no_skip_qa() -> None:
    assert "skip-qa" not in ACTIONS
    assert "skip-qa" in FORBIDDEN_ACTIONS
    catalog = client.get("/api/skills").json()
    assert "skip-qa" not in catalog["actions"]
    denied = client.post("/api/skills/skip-qa", json={"job_id": "x"})
    assert denied.status_code == 400
