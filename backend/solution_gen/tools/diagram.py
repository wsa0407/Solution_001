from __future__ import annotations

from typing import Any

from solution_gen.chat.diagram import label_of, resolve_chapter
from solution_gen.domain import DiagramKind, DiagramRequest, JobStatus
from solution_gen.pipeline.machine import TransitionError
from solution_gen.service import JobService
from solution_gen.skills import raster
from solution_gen.skills.svghtml import HtmlDiagramError, extract_inline_svg
from solution_gen.store import output_dir, save_job
from solution_gen.tools.result import fail, snapshot

_svc = JobService()


def _req(job, kind: str):
    dk = DiagramKind(kind)
    return next((r for r in job.diagram_requests if r.kind is dk), None)


def request_diagram(
    job_id: str,
    kind: str,
    placement: str = "",
    reference: str = "",
    chapter_id: str = "",
) -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("仅正文齐后可出图。", job)
    try:
        dk = DiagramKind(kind)
    except ValueError:
        return fail("图类型只能是 architecture / flowchart / gantt。", job)
    req = DiagramRequest(kind=dk, placement=placement, reference=reference or "按正文生成")
    req.chapter_id = chapter_id or resolve_chapter(job, placement or reference, dk)
    req.status = "selected"
    job.diagram_requests = [r for r in job.diagram_requests if r.kind != dk]
    job.diagram_requests.append(req)
    save_job(job)
    if not req.chapter_id:
        return snapshot(job, replies=[f"需要{label_of(dk)}。请说明放在哪一章后面。"], next="ask_placement")
    return snapshot(
        job,
        replies=[f"已记下{label_of(dk)}（{req.chapter_id}）。请 draft-diagram-spec 生成文字说明。"],
        next="draft_diagram_spec",
    )


def draft_diagram_spec(job_id: str, kind: str, text: str = "", placement: str = "") -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("仅正文齐后可出图。", job)
    try:
        dk = DiagramKind(kind)
    except ValueError:
        return fail("图类型只能是 architecture / flowchart / gantt。", job)
    req = next((r for r in job.diagram_requests if r.kind is dk), None)
    if req is None:
        req = DiagramRequest(kind=dk, placement=placement)
        job.diagram_requests.append(req)
    hint = placement or req.placement or text
    if placement:
        req.placement = placement
    if placement or not req.chapter_id:
        req.chapter_id = resolve_chapter(job, hint, dk)
    operator = (text or "").strip()
    if operator and operator != "按正文生成":
        req.spec_text = text
    else:
        chapter = next((c for c in job.chapters if c.id == req.chapter_id), None)
        title = chapter.title if chapter else ""
        excerpt = ((chapter.content or "") if chapter else "")[:400]
        req.spec_text = f"【{label_of(dk)}】挂在《{title}》后。根据正文：{excerpt}"
    req.status = "spec_pending"
    save_job(job)
    return snapshot(job, replies=[req.spec_text], next="wait_confirm_diagram")


def confirm_diagram_spec(job_id: str, kind: str) -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("仅正文齐后可出图。", job)
    req = _req(job, kind)
    if req is None or not (req.spec_text or "").strip():
        return fail("请先生成文字说明。", job)
    req.status = "confirmed"
    save_job(job)
    return snapshot(job, replies=["说明已确认。请按 diagram-design 出 HTML 后 attach-diagram。"], next="attach_diagram")


def attach_diagram(job_id: str, kind: str, html: str = "") -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("仅正文齐后可出图。", job)
    req = _req(job, kind)
    if req is None or req.status != "confirmed":
        return fail("未确认说明，不能出图。", job)
    try:
        svg = extract_inline_svg(html)
    except HtmlDiagramError as exc:
        return fail(str(exc), job)
    dest = output_dir(job.id) / f"{req.chapter_id}.png"
    try:
        raster.svg_to_png(svg, dest)
    except Exception as exc:
        return fail(str(exc), job)
    html_path = output_dir(job.id) / f"{req.chapter_id}-{req.kind.value}.html"
    html_path.write_text(html, encoding="utf-8")
    chapter = next((c for c in job.chapters if c.id == req.chapter_id), None)
    if chapter is not None:
        chapter.diagram = True
        if "【图" not in (chapter.content or ""):
            chapter.content = (chapter.content or "").rstrip() + f"\n\n【图 {chapter.id}】"
    req.status = "drawn"
    save_job(job)
    return snapshot(job, replies=["图已挂上。任务仍停在询问配图。"], next="wait_next_diagram")


def skip_diagrams(job_id: str) -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("当前不能跳过出图。", job)
    try:
        job = _svc.skip_diagrams(job_id)
        # skip_diagrams only moves to QA_RUNNING; polish/QA is a separate skill.
    except TransitionError as exc:
        return fail(str(exc), _svc.get(job_id))
    return snapshot(job, replies=["已跳过出图（不是跳过质检）。请调用 polish-deliver 开始核对。"], next="polish_deliver")


async def emit_diagrams(job_id: str) -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("仅正文齐后可出图。", job)
    drawn = [r for r in job.diagram_requests if r.status == "drawn"]
    if not drawn:
        return fail("还没有已出图。先确认说明并 attach-diagram，或 skip-diagrams。", job)
    job.diagram_requests = drawn
    save_job(job)
    try:
        job = _svc.begin_diagrams(job_id)
        job = await _svc.run_diagrams(job_id)
    except TransitionError as exc:
        return fail(str(exc), _svc.get(job_id))
    return snapshot(job, replies=["出图流程已结束。质检不能跳过，请看 qa_issues 后 polish-deliver。"], next="polish_deliver")
