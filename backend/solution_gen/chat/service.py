from __future__ import annotations

from typing import Any

from solution_gen.chat.brief import (
    infer_doc_type,
    is_complete,
    is_greeting,
    merge_from_text,
    missing_fields,
    next_question,
    recap,
)
from solution_gen.chat.diagram import wants_emit
from solution_gen.chat.intent import Intent, classify, diagram_kinds_in
from solution_gen.chat.outline_edit import apply_outline_instruction
from solution_gen.domain import (
    ChatMessage,
    Job,
    JobStatus,
    PendingConfirm,
    Profile,
)
from solution_gen.genre import apply_pack
from solution_gen.labels import STAGE_LABEL

_BUSY = {
    JobStatus.OUTLINE_DRAFT,
    JobStatus.GENERATING,
    JobStatus.DIAGRAM_RUNNING,
    JobStatus.QA_RUNNING,
    JobStatus.ASSEMBLING,
    JobStatus.REVISING,
}

def _reply(job: Job, texts: list[str], **extra: Any) -> dict[str, Any]:
    for t in texts:
        job.chat_log.append(ChatMessage(role="assistant", text=t))
    from solution_gen.store import save_job

    save_job(job)
    return {
        "job": job,
        "replies": [{"role": "assistant", "text": t} for t in texts],
        "pending_confirm": job.pending_confirm.value if job.pending_confirm else None,
        "diagram_prompt": extra.get("diagram_prompt"),
        "start_generation": extra.get("start_generation", False),
        "start_qa": extra.get("start_qa", False),
        "start_diagrams": extra.get("start_diagrams", False),
        "stage": STAGE_LABEL.get(job.status, str(job.status)),
    }


async def handle_chat(svc: Any, job_id: str, text: str) -> dict[str, Any]:
    job: Job = svc.get(job_id)
    text = (text or "").strip()
    if not text:
        return _reply(job, ["请用一句话说需求，或回复当前问的那一项。"])
    job.chat_log.append(ChatMessage(role="user", text=text))
    from solution_gen.store import save_job

    save_job(job)

    intent = classify(text, job.status, job.pending_confirm)

    if intent is Intent.SKIP_QA:
        return _reply(job, ["质检不能跳过。只能改写问题章，或更换产品库素材。"])

    if intent is Intent.NEW_JOB:
        created = svc.create(job.doc_type, owner=job.owner)
        return _reply(
            created,
            ["已新开一份。请说要写什么文档，例如：帮我写一份项目建议书。"],
        )

    if intent is Intent.CONFIRM:
        return await _do_confirm(svc, job)

    if job.status is JobStatus.PROFILE:
        return _collect(svc, job, text)

    if job.status is JobStatus.OUTLINE_CONFIRM:
        return _edit_or_wait_outline(svc, job, text)

    if job.status is JobStatus.DIAGRAM_ASK:
        return _diagram_talk(svc, job, text, intent)

    if job.status is JobStatus.QA_BLOCKED:
        return _qa_talk(svc, job, text)

    if job.status is JobStatus.FINAL_CONFIRM:
        return await _final_talk(svc, job, text)

    if job.status in _BUSY:
        return _reply(job, [f"{STAGE_LABEL.get(job.status)}，请稍候。现在回复「确认」不会生效。"])

    if job.status is JobStatus.DELIVERED:
        return _reply(job, ["这份已经交付。要再写一份，请说「新开一份」。"])

    return _reply(job, ["我记下了。若要改目录、改正文或确认，请直接说。"])


def _collect(svc: Any, job: Job, text: str) -> dict[str, Any]:
    if is_greeting(text) and not (job.profile and job.profile.project_name):
        return _reply(job, ["请用一句话说需求，例如：帮我写一份青岛的项目建议书。"])
    dtype = infer_doc_type(text)
    if dtype:
        job.doc_type = dtype
    current = job.profile or Profile()
    miss = missing_fields(current)
    expecting = miss[0] if miss else None
    job.profile = merge_from_text(current, text, expecting=expecting)
    if is_complete(job.profile):
        job.profile = apply_pack(job.profile)
        job.brief_complete = True
        job.pending_confirm = PendingConfirm.BRIEF
        return _reply(job, [recap(job.profile, job)])
    job.pending_confirm = None
    job.brief_complete = False
    q = next_question(job.profile)
    return _reply(job, [q or "请再补充一项关键信息。"])


async def _do_confirm(svc: Any, job: Job) -> dict[str, Any]:
    if job.status is JobStatus.DIAGRAM_ASK:
        pending_req = next((r for r in job.diagram_requests if r.status == "spec_pending"), None)
        if pending_req is None:
            return _reply(job, ["请先起草图说明，再回复「确认」。"])
        from solution_gen.tools.diagram import confirm_diagram_spec

        result = confirm_diagram_spec(job.id, pending_req.kind.value)
        job = svc.get(job.id)
        replies = result.get("replies") or [result.get("error") or "说明已确认。"]
        return _reply(job, replies)
    pending = job.pending_confirm
    if pending is PendingConfirm.BRIEF:
        if not job.profile or not is_complete(job.profile):
            job.pending_confirm = None
            return _reply(job, [next_question(job.profile or Profile()) or "还缺关键信息，先补齐再确认。"])
        job.pending_confirm = None
        job = await svc.submit_profile(job.id, job.profile)
        job.pending_confirm = PendingConfirm.OUTLINE
        titles = "、".join(f"{i+1}.{c.title}" for i, c in enumerate(job.chapters))
        return _reply(
            job,
            [
                "正在起草目录。",
                f"目录草案：{titles}。回复「确认」开始写正文，或直接说怎么改目录。",
            ],
        )
    if pending is PendingConfirm.OUTLINE and job.status is JobStatus.OUTLINE_CONFIRM:
        job.pending_confirm = None
        job = svc.confirm_outline(job.id)
        return _reply(job, ["目录已确认，开始按章写正文。"], start_generation=True)
    if pending is PendingConfirm.FINAL and job.status is JobStatus.FINAL_CONFIRM:
        if not job.export_path:
            return _reply(job, ["文稿还没有组装完成，暂时不能确认交付。"])
        job.pending_confirm = None
        job = svc.deliver(job.id)
        return _reply(job, ["终稿已确认交付。"])
    return _reply(job, ["现在还不能确认。等我请你确认目录或终稿时，再回复「确认」。"])


def _edit_or_wait_outline(svc: Any, job: Job, text: str) -> dict[str, Any]:
    changed = apply_outline_instruction(job.chapters, text)
    if not changed:
        return _reply(job, ["目录还在待确认。直接说怎么改（例如把实施计划拆成两章），或回复「确认」。"])
    job = svc.update_outline(job.id, changed)
    job.pending_confirm = PendingConfirm.OUTLINE
    titles = "、".join(f"{i+1}.{c.title}" for i, c in enumerate(job.chapters))
    return _reply(job, [f"已按你的话改目录：{titles}。回复「确认」开始写正文。"])


def _diagram_talk(svc: Any, job: Job, text: str, intent: Intent) -> dict[str, Any]:
    if intent is Intent.SKIP_DIAGRAMS:
        job = svc.skip_diagrams(job.id)
        return _reply(job, ["好，先不出图，开始按规则核对正文。"], start_qa=True)

    if wants_emit(text):
        drawn = [r for r in job.diagram_requests if r.status == "drawn"]
        if not drawn:
            return _reply(job, ["请先确认说明并出图。"], start_diagrams=False)
        return _reply(job, ["请调用 emit-diagrams 收口已出图。"], start_diagrams=False)

    kinds = diagram_kinds_in(text)
    if intent is Intent.WANT_DIAGRAM or kinds:
        from solution_gen.tools.diagram import draft_diagram_spec

        replies: list[str] = []
        for kind in kinds:
            result = draft_diagram_spec(job.id, kind.value)
            replies.extend(result.get("replies") or [])
        job = svc.get(job.id)
        if not replies:
            replies = ["已起草图说明，请确认或修改。"]
        return _reply(job, replies)

    return _reply(job, ["需要架构图、流程图还是甘特图？也可以回复「都不要」。"])


def _qa_talk(svc: Any, job: Job, text: str) -> dict[str, Any]:
    issue = job.qa_issues[0] if job.qa_issues else None
    chapter_id = issue.chapter_id if issue else (job.chapters[0].id if job.chapters else "")
    if "换" in text and ("素材" in text or "白皮书" in text):
        job = svc.swap_material(job.id, chapter_id, text)
        return _reply(job, ["已换素材，正在重跑问题章。"], start_generation=True)
    if chapter_id:
        job = svc.rewrite(job.id, chapter_id, text)
        return _reply(job, ["已记下改法，正在重跑问题章。"], start_generation=True)
    return _reply(job, ["请说明改哪一章、怎么改。不能跳过质检。"])


async def _final_talk(svc: Any, job: Job, text: str) -> dict[str, Any]:
    job = svc.revise(job.id, text)
    return _reply(job, ["按你的话修订并复检。"], start_generation=True)
