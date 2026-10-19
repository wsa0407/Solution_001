from __future__ import annotations

from solution_gen.domain import Chapter, DocType, Job, Profile
from solution_gen.genre.contracts import CONTRACTS, WRITING
from solution_gen.genre.models import GenreContract
from solution_gen.genre.packs import (
    apply_pack,
    closer_sentence,
    has_civil,
    kind_label,
    resolve_pack,
    selected_modules,
)

__all__ = [
    "apply_pack",
    "build_outline",
    "closer_sentence",
    "contract_for",
    "describe",
    "has_civil",
    "honors_contract",
    "required_titles",
    "resolve_pack",
    "selected_modules",
    "writing_for",
]


def contract_for(doc_type: DocType | str) -> GenreContract:
    key = doc_type.value if isinstance(doc_type, DocType) else str(doc_type)
    return CONTRACTS.get(key) or CONTRACTS["solution"]


def _include(when: str | None, profile: Profile) -> bool:
    if not when:
        return True
    if when == "has_civil":
        return has_civil(profile)
    return True


def _module_brief(profile: Profile) -> str:
    mods = selected_modules(profile)
    closer = closer_sentence(profile)
    if not mods:
        return f"建设内容按需求展开：{profile.need or closer}"
    lines = [f"建设内容收口：{closer}。已选模块："]
    for m in mods:
        lines.append(f"- {m.title}（{kind_label(m.kind)}）{m.brief}")
    if profile.scenes:
        lines.append("场景：" + "、".join(profile.scenes))
    return "\n".join(lines)


def _chapter_brief(profile: Profile, writing: str, nest: bool) -> str:
    closer = closer_sentence(profile)
    extra = _module_brief(profile) if nest or writing in {"overview", "conclusion", "scheme", "overall"} else ""
    base = WRITING.get(writing, "")
    bits = [base]
    if extra:
        bits.append(extra)
    elif closer and writing in {"overview", "conclusion"}:
        bits.append(f"建设内容收口：{closer}")
    if profile.budget is not None and writing in {"overview", "investment", "economy", "conclusion", "schedule_budget"}:
        bits.append(f"总投资 {profile.budget:g} 万元，须与全文一致。")
    if profile.funding_source and writing in {"overview", "investment", "conclusion"}:
        bits.append(f"资金来源：{profile.funding_source}。")
    if profile.construction_period is not None and writing in {"overview", "implementation", "schedule_budget", "conclusion"}:
        bits.append(f"建设周期 {profile.construction_period} 个月。")
    return "\n".join(b for b in bits if b)


def build_outline(profile: Profile, doc_type: DocType | str) -> list[Chapter]:
    profile = apply_pack(profile)
    contract = contract_for(doc_type)
    templates = [t for t in contract.chapters if _include(t.when, profile)]
    chapters: list[Chapter] = []
    for i, spec in enumerate(templates):
        cid = f"c{i+1}"
        chapters.append(
            Chapter(
                id=cid,
                title=spec.title,
                words=spec.words,
                diagram=spec.diagram,
                brief=_chapter_brief(profile, spec.writing, spec.nest_modules),
                writing=spec.writing,
                depends_on=[] if i == 0 else [f"c{i}"],
            )
        )
    return chapters


def required_titles(profile: Profile, doc_type: DocType | str) -> list[str]:
    contract = contract_for(doc_type)
    return [t.title for t in contract.chapters if t.required and _include(t.when, profile)]


def honors_contract(chapters: list[Chapter] | None, profile: Profile, doc_type: DocType | str) -> bool:
    if not chapters or len(chapters) < 3:
        return False
    titles = " ".join(c.title for c in chapters)
    needed = required_titles(profile, doc_type)
    return all(title in titles for title in needed)


def writing_for(chapter: Chapter) -> str:
    if chapter.writing:
        return WRITING.get(chapter.writing, "")
    return ""


def describe(job: Job) -> dict:
    profile = job.profile or Profile()
    contract = contract_for(job.doc_type)
    pack = resolve_pack(profile) if job.profile else None
    mods = selected_modules(profile) if job.profile else []
    return {
        "name": contract.name,
        "pack": pack.name if pack else None,
        "pack_id": pack.id if pack else None,
        "closer": closer_sentence(profile) if job.profile else "",
        "modules": [{"id": m.id, "title": m.title, "kind": m.kind} for m in mods],
        "module_options": (
            [{"id": m.id, "title": m.title, "kind": m.kind} for m in pack.modules] if pack else []
        ),
        "default_diagrams": list(contract.default_diagrams),
    }
