from __future__ import annotations

import asyncio

from solution_gen.chat.service import handle_chat
from solution_gen.domain import Chapter, DiagramKind, DiagramRequest, JobStatus, Profile
from solution_gen.service import JobService
from solution_gen.store import save_job
from solution_gen.tools.dispatch import dispatch


def _pad(title: str) -> str:
    return f"{title}。乐山市建设内容。" * 80


def _ask_job() -> tuple[JobService, str]:
    svc = JobService()
    job = svc.create()
    job.profile = Profile(place="乐山市", industry="低空经济", project_name="乐山市低空经济基础设施建设项目")
    job.chapters = [
        Chapter(id="c1", title="项目概述", content=_pad("项目概述"), status="done"),
        Chapter(id="c4", title="总体架构", content=_pad("总体架构"), status="done", diagram=True),
        Chapter(id="c7", title="实施计划", content=_pad("实施计划"), status="done"),
    ]
    job.status = JobStatus.DIAGRAM_ASK
    save_job(job)
    return svc, job.id


def test_skip_diagrams_goes_to_qa() -> None:
    svc, jid = _ask_job()
    result = asyncio.run(handle_chat(svc, jid, "都不要"))
    assert result["job"].status is JobStatus.QA_RUNNING
    assert result["start_qa"] is True
    assert not any((c.diagram_json or {}).get("image_data") for c in result["job"].chapters)


def test_want_diagram_without_placement_stays_ask() -> None:
    svc, jid = _ask_job()
    result = asyncio.run(handle_chat(svc, jid, "要架构图"))
    job = result["job"]
    assert job.status is JobStatus.DIAGRAM_ASK
    assert result.get("start_diagrams") is False
    assert any(r.kind is DiagramKind.ARCHITECTURE for r in job.diagram_requests)
    assert not job.diagram_requests[0].placement
    again = asyncio.run(handle_chat(svc, jid, "按这些出图"))
    assert again["job"].status is JobStatus.DIAGRAM_ASK
    assert again.get("start_diagrams") is False


def test_chat_confirm_confirms_diagram_spec_not_deliver() -> None:
    svc, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    result = asyncio.run(handle_chat(svc, jid, "确认"))
    assert result["job"].status is JobStatus.DIAGRAM_ASK
    assert result["job"].diagram_requests[0].status == "confirmed"
    assert result.get("start_diagrams") is not True


def test_diagram_request_has_spec_text_and_selected_status() -> None:
    req = DiagramRequest(kind=DiagramKind.ARCHITECTURE)
    assert req.spec_text == ""
    assert req.status == "selected"


def test_attach_without_confirm_fails() -> None:
    _, jid = _ask_job()
    asyncio.run(dispatch("request-diagram", {"job_id": jid, "kind": "architecture"}))
    result = asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": "<svg xmlns='http://www.w3.org/2000/svg'></svg>"}))
    assert result["ok"] is False
    assert "确认" in result["error"]


def test_emit_without_drawn_fails() -> None:
    _, jid = _ask_job()
    result = asyncio.run(dispatch("emit-diagrams", {"job_id": jid}))
    assert result["ok"] is False


def test_draft_confirm_attach_stays_diagram_ask(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster
    from solution_gen.store import output_dir

    def fake_png(svg: str, dest: Path) -> None:
        dest.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
            b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    monkeypatch.setattr(raster, "svg_to_png", fake_png)
    _, jid = _ask_job()
    drafted = asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    assert drafted["ok"]
    assert drafted["status"] == "diagram_ask"
    reqs = drafted["diagram_requests"]
    assert reqs[0]["status"] == "spec_pending"
    assert reqs[0]["spec_text"]
    confirmed = asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    assert confirmed["ok"]
    html = "<html><body><svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'><rect width='8' height='8' fill='#000'/></svg></body></html>"
    attached = asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    assert attached["ok"]
    assert attached["status"] == "diagram_ask"
    assert attached["diagram_requests"][0]["status"] == "drawn"
    png = output_dir(jid) / "c4.png"
    assert png.exists()


def test_draft_keeps_requested_chapter_id() -> None:
    _, jid = _ask_job()
    requested = asyncio.run(
        dispatch("request-diagram", {"job_id": jid, "kind": "architecture", "placement": "实施计划"})
    )
    assert requested["ok"]
    assert requested["diagram_requests"][0]["chapter_id"] == "c7"
    drafted = asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    assert drafted["ok"]
    req = drafted["diagram_requests"][0]
    assert req["chapter_id"] == "c7"
    assert "实施计划" in req["spec_text"]


def test_second_kind_cannot_attach_before_its_confirm(monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster

    monkeypatch.setattr(raster, "svg_to_png", lambda svg, dest: Path(dest).write_bytes(b"PNG"))
    _, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    html = "<html><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    result = asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "gantt", "html": html}))
    assert result["ok"] is False


def test_skip_keeps_drawn(monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster
    from solution_gen.tools.diagram import skip_diagrams

    monkeypatch.setattr(raster, "svg_to_png", lambda svg, dest: Path(dest).write_bytes(b"PNG"))
    _, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    html = "<html><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    skipped = skip_diagrams(jid)
    assert skipped["ok"]
    assert skipped["status"] == "qa_running"
    assert any(r["status"] == "drawn" for r in skipped["diagram_requests"])


def test_emit_after_drawn_enters_qa(monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster

    async def _stay_qa_running(self, job_id: str):
        return self.get(job_id)

    monkeypatch.setattr(raster, "svg_to_png", lambda svg, dest: Path(dest).write_bytes(b"PNG"))
    monkeypatch.setattr(JobService, "run_qa", _stay_qa_running)
    svc, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    html = "<html><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    job = svc.get(jid)
    next(c for c in job.chapters if c.id == "c7").diagram = True
    save_job(job)
    emitted = asyncio.run(dispatch("emit-diagrams", {"job_id": jid}))
    assert emitted["ok"]
    assert emitted["status"] == "qa_running"
    chapters = {c.id: c for c in svc.get(jid).chapters}
    assert chapters["c4"].diagram is True
    assert chapters["c7"].diagram is False


def test_assemble_does_not_overwrite_attached_png() -> None:
    from solution_gen.assemble import assemble
    from solution_gen.store import output_dir

    sentinel = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    svc, jid = _ask_job()
    job = svc.get(jid)
    png_path = output_dir(jid) / "c4.png"
    png_path.write_bytes(sentinel)
    c4 = next(c for c in job.chapters if c.id == "c4")
    c4.diagram = True
    c4.diagram_json = {}
    assemble(job)
    assert png_path.read_bytes() == sentinel


def test_export_docx_embeds_png(tmp_path, monkeypatch) -> None:
    from docx import Document
    from solution_gen.domain import DocType, Job
    from solution_gen.skills.document import export_docx

    job = Job(
        id="jpng",
        doc_type=DocType.SOLUTION,
        status=JobStatus.DELIVERED,
        profile=Profile(place="乐山市", industry="低空经济", project_name="乐山项目"),
        chapters=[Chapter(id="c4", title="项目建设方案", content="建设方案正文。乐山市建设内容。", diagram=True)],
    )
    monkeypatch.setattr("solution_gen.skills.document.output_dir", lambda job_id: tmp_path)
    png = tmp_path / "c4.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    out = tmp_path / "out.docx"
    export_docx(job, out)
    doc = Document(str(out))
    assert any(p._element.xpath(".//*[local-name()='drawing']") for p in doc.paragraphs)

