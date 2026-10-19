from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from solution_gen.config import settings
from solution_gen.domain import Job

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            owner TEXT,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    return conn


def _dump(job: Job) -> str:
    if hasattr(job, "model_dump_json"):
        return job.model_dump_json()
    return job.json()


def _load(raw: str) -> Job:
    data = json.loads(raw)
    if isinstance(data.get("profile"), dict):
        data["profile"] = {k: v for k, v in data["profile"].items() if v is not None or k in {"budget", "construction_period"}}
    return Job.model_validate(data) if hasattr(Job, "model_validate") else Job(**data)


def save_job(job: Job) -> Job:
    job.updated_at = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO jobs(id, owner, payload, updated_at) VALUES (?,?,?,?)",
            (job.id, job.owner, _dump(job), job.updated_at),
        )
        conn.commit()
        conn.close()
    return job


def get_job(job_id: str) -> Job:
    conn = _connect()
    row = conn.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise KeyError(job_id)
    return _load(row[0])


def list_jobs(owner: str | None = None) -> list[Job]:
    conn = _connect()
    if owner:
        rows = conn.execute("SELECT payload FROM jobs WHERE owner=? ORDER BY updated_at DESC", (owner,)).fetchall()
    else:
        rows = conn.execute("SELECT payload FROM jobs ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [_load(r[0]) for r in rows]


def output_dir(job_id: str) -> Path:
    path = settings.outputs_dir / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path
