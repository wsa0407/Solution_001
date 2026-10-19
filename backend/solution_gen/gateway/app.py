from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from solution_gen.service import JobService
from solution_gen.tools.dispatch import ACTIONS, dispatch
from solution_gen.view import job_payload

svc = JobService()
app = FastAPI(title="方案生产台", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    return HTMLResponse(
        '<!doctype html><meta charset=utf-8><p>对话在 <a href="http://127.0.0.1:3080/">http://127.0.0.1:3080/</a>。本端口只提供 skill API。</p>'
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "role": "skill-backend", "ui": "dsh-web"}


@app.post("/api/skills/{action}")
async def skill_action(action: str, body: dict[str, Any] | None = None) -> dict:
    result = await dispatch(action, body or {})
    key = action.replace("_", "-").lower()
    if key in {"skip-qa", "skipqa"}:
        raise HTTPException(400, result.get("error") or "没有 skip-qa 工具")
    if not result.get("ok") and result.get("error") == "job not found":
        raise HTTPException(404, "job not found")
    return result


@app.get("/api/skills")
def skill_catalog() -> dict:
    return {"actions": sorted(ACTIONS), "forbidden": ["skip-qa"]}


@app.get("/api/jobs")
def list_jobs(owner: str | None = Query(default=None)) -> list[dict]:
    return [job_payload(j) for j in svc.list(owner)]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    try:
        return job_payload(svc.get(job_id))
    except KeyError as exc:
        raise HTTPException(404, "job not found") from exc


@app.get("/api/jobs/{job_id}/export")
def export_job(job_id: str):
    try:
        job = svc.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "job not found") from exc
    if not job.export_path or not Path(job.export_path).exists():
        raise HTTPException(404, "尚未组装 Word")
    return FileResponse(
        job.export_path,
        filename=Path(job.export_path).name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
