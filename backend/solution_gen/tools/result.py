from __future__ import annotations

from typing import Any

from solution_gen.domain import Job
from solution_gen.genre import describe
from solution_gen.view import job_payload


def snapshot(job: Job, **extra: Any) -> dict[str, Any]:
    payload = job_payload(job)
    chapters = [
        {
            "id": c.id,
            "title": c.title,
            "status": c.status,
            "words": c.words,
            "has_content": bool(c.content),
        }
        for c in job.chapters
    ]
    issues = [
        {"code": i.code, "chapter_id": i.chapter_id, "detail": i.detail, "dimension": i.dimension}
        for i in job.qa_issues
    ]
    data: dict[str, Any] = {
        "ok": True,
        "error": None,
        "job_id": job.id,
        "doc_type": job.doc_type.value if hasattr(job.doc_type, "value") else str(job.doc_type),
        "status": str(job.status),
        "stage": payload["stage"],
        "hint": payload["hint"],
        "title": payload["title"],
        "pending_confirm": payload["pending_confirm"],
        "brief_complete": job.brief_complete,
        "export_path": job.export_path,
        "chapters": chapters,
        "qa_issues": issues,
        "profile": payload.get("profile"),
        "genre": describe(job),
        "diagram_requests": [
            {
                "kind": r.kind.value if hasattr(r.kind, "value") else str(r.kind),
                "status": r.status,
                "chapter_id": r.chapter_id,
                "placement": r.placement,
                "spec_text": r.spec_text,
            }
            for r in job.diagram_requests
        ],
    }
    data.update(extra)
    return data


def fail(message: str, job: Job | None = None, **extra: Any) -> dict[str, Any]:
    data = snapshot(job) if job is not None else {"job_id": extra.get("job_id")}
    data["ok"] = False
    data["error"] = message
    data.update(extra)
    return data
