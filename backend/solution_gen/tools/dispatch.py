from __future__ import annotations

from typing import Any

from solution_gen.pipeline.machine import TransitionError
from solution_gen.tools.brief import collect_brief, create_job, draft_outline, job_status
from solution_gen.tools.chapter import write_chapters
from solution_gen.tools.diagram import (
    attach_diagram,
    confirm_diagram_spec,
    draft_diagram_spec,
    emit_diagrams,
    request_diagram,
    skip_diagrams,
)
from solution_gen.tools.outline import edit_outline
from solution_gen.tools.polish import polish_deliver
from solution_gen.tools.result import fail

ACTIONS = frozenset(
    {
        "create-job",
        "status",
        "collect-brief",
        "draft-outline",
        "edit-outline",
        "write-chapters",
        "request-diagram",
        "draft-diagram-spec",
        "confirm-diagram-spec",
        "attach-diagram",
        "skip-diagrams",
        "emit-diagrams",
        "polish-deliver",
        "rewrite-chapter",
        "swap-material",
        "revise",
        "deliver",
    }
)

FORBIDDEN_ACTIONS = frozenset({"skip-qa", "skip_qa", "skipqa"})


def _norm(action: str) -> str:
    return (action or "").strip().lower().replace("_", "-")


async def dispatch(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Single entry for CLI and HTTP. skip-qa is not a tool."""
    body = dict(payload or {})
    key = _norm(action)
    if key in FORBIDDEN_ACTIONS:
        return fail("没有 skip-qa 工具。质检失败只能 rewrite 或 swap-material。")
    if key not in ACTIONS:
        return fail(f"未知工具: {action}。允许: {', '.join(sorted(ACTIONS))}。")

    job_id = str(body.get("job_id") or "")
    try:
        if key == "create-job":
            return create_job(str(body.get("doc_type") or "solution"), str(body.get("owner") or "dsh"))
        if key == "status":
            return job_status(job_id)
        if key == "collect-brief":
            return collect_brief(
                job_id=job_id or None,
                text=str(body.get("text") or ""),
                doc_type=body.get("doc_type"),
                owner=str(body.get("owner") or "dsh"),
                project_name=body.get("project_name"),
                place=body.get("place"),
                construction_unit=body.get("construction_unit"),
                budget=body.get("budget"),
                construction_period=body.get("construction_period"),
                industry=body.get("industry"),
                need=body.get("need"),
                compilation_unit=body.get("compilation_unit"),
                funding_source=body.get("funding_source"),
                modules=body.get("modules"),
            )
        if key == "draft-outline":
            return await draft_outline(job_id)
        if key == "edit-outline":
            return edit_outline(job_id, str(body.get("text") or ""))
        if key == "write-chapters":
            return await write_chapters(job_id)
        if key == "request-diagram":
            return request_diagram(
                job_id,
                str(body.get("kind") or ""),
                placement=str(body.get("placement") or ""),
                reference=str(body.get("reference") or ""),
                chapter_id=str(body.get("chapter_id") or ""),
            )
        if key == "draft-diagram-spec":
            return draft_diagram_spec(
                job_id,
                str(body.get("kind") or ""),
                text=str(body.get("text") or ""),
                placement=str(body.get("placement") or ""),
            )
        if key == "confirm-diagram-spec":
            return confirm_diagram_spec(job_id, str(body.get("kind") or ""))
        if key == "attach-diagram":
            return attach_diagram(job_id, str(body.get("kind") or ""), html=str(body.get("html") or ""))
        if key == "skip-diagrams":
            return skip_diagrams(job_id)
        if key == "emit-diagrams":
            return await emit_diagrams(job_id)
        if key == "rewrite-chapter":
            return await polish_deliver(
                job_id,
                op="rewrite",
                chapter_id=str(body.get("chapter_id") or ""),
                instruction=str(body.get("instruction") or body.get("text") or ""),
            )
        if key == "swap-material":
            return await polish_deliver(
                job_id,
                op="swap",
                chapter_id=str(body.get("chapter_id") or ""),
                material_title=str(body.get("material_title") or body.get("title") or ""),
                instruction=str(body.get("instruction") or body.get("text") or ""),
            )
        if key == "revise":
            return await polish_deliver(job_id, op="revise", instruction=str(body.get("instruction") or body.get("text") or ""))
        if key == "deliver":
            return await polish_deliver(job_id, op="deliver")
        return await polish_deliver(
            job_id,
            op=str(body.get("op") or "run-qa"),
            chapter_id=str(body.get("chapter_id") or ""),
            instruction=str(body.get("instruction") or body.get("text") or ""),
            material_title=str(body.get("material_title") or ""),
        )
    except KeyError:
        return fail("job not found", job_id=job_id)
    except TransitionError as exc:
        return fail(str(exc), job_id=job_id)
    except ValueError as exc:
        return fail(str(exc), job_id=job_id)
