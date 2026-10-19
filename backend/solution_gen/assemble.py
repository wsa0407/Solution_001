from __future__ import annotations

from solution_gen.domain import Job, Snapshot
from solution_gen.skills.document import export_docx
from solution_gen.store import output_dir
from solution_gen.workers.numbering import align_job_numbering
from solution_gen.workers.prose import is_chapter_prose


def assemble(job: Job) -> Job:
    align_job_numbering(job)
    out = output_dir(job.id)
    for ch in job.chapters:
        if not ch.diagram:
            continue
        png_path = out / f"{ch.id}.png"
        if png_path.exists():
            if is_chapter_prose(ch.content) and "【图" not in ch.content and "[DIAGRAM]" not in ch.content:
                ch.content += f"\n【图 {ch.id}】\n"
            continue
        # no confirmed PNG: do not invent charts color-box
        continue
    docx_path = out / f"{job.id}.docx"
    export_docx(job, docx_path)
    job.export_path = str(docx_path)
    job.snapshots.append(Snapshot(at=job.updated_at, status=str(job.status), note="组装出稿"))
    return job
