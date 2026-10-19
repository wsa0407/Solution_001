from __future__ import annotations

import re

from solution_gen.domain import DOC_TYPE_LABEL, DocType, Job, Profile
from solution_gen.genre import apply_pack, describe, resolve_pack
from solution_gen.genre.packs import PACKS

REQUIRED = (
    "project_name",
    "place",
    "construction_unit",
    "budget",
    "construction_period",
)

_QUESTIONS = {
    "project_name": "项目全称是什么？",
    "place": "项目在哪个市或县？",
    "construction_unit": "建设单位是哪家？",
    "budget": "总投资大约多少万元？",
    "construction_period": "建设周期多少个月？",
}

_DOC_HINTS = (
    (DocType.FEASIBILITY, ("可研", "可行性研究")),
    (DocType.INITIATION, ("立项",)),
    (DocType.SOLUTION, ("建议书", "解决方案", "方案")),
)

_INDUSTRY_ONLY = {pack.name for pack in PACKS} | {a for pack in PACKS for a in pack.aliases}
_NOT_A_SLOT = ("帮我写", "确认", "新开一份", "跳过", "都不要")
_GREETINGS = {"你好", "您好", "hello", "hi", "在吗", "哈喽", "嗨"}


def is_greeting(text: str) -> bool:
    return (text or "").strip().lower() in {g.lower() for g in _GREETINGS}


def infer_doc_type(text: str) -> DocType | None:
    for dtype, keys in _DOC_HINTS:
        if any(k in text for k in keys):
            return dtype
    return None


def merge_from_text(profile: Profile, text: str, expecting: str | None = None) -> Profile:
    raw = text.strip()
    if not profile.need:
        profile.need = raw
    elif raw and raw not in profile.need:
        profile.need = f"{profile.need}\n{raw}"

    name = re.search(r"(?:项目(?:名称|叫|为)|名为|叫做)\s*[「『《]?([^」』》\n]{4,40})", raw)
    if name:
        profile.project_name = name.group(1).strip()
    quoted = re.search(r"[「『《]([^」』》]{4,40})[」』》]", raw)
    if quoted and not profile.project_name:
        profile.project_name = quoted.group(1).strip()
    if "项目" in raw and len(raw) <= 40 and not profile.project_name and "帮我" not in raw:
        if re.search(r"[\u4e00-\u9fff]{4,}项目", raw):
            profile.project_name = raw

    places = re.findall(r"(?=([\u4e00-\u9fff]{2,3}(?:市|县)))", raw)
    for cand in places:
        if "建设" in cand or any(ch in cand[:-1] for ch in "在的于属"):
            continue
        profile.place = cand
        break

    unit = re.search(r"([\u4e00-\u9fff]{2,30}(?:公司|局|院|集团|中心))", raw)
    if unit and "建设周期" not in unit.group(1) and "编制" not in unit.group(1):
        profile.construction_unit = unit.group(1)

    compiler = re.search(r"编制单位[为是：:\s]*([^\n。；]{2,40})", raw)
    if compiler:
        profile.compilation_unit = compiler.group(1).strip()

    fund = re.search(r"资金来源[为是：:\s]*([^\n。；]{2,40})", raw)
    if fund:
        profile.funding_source = fund.group(1).strip()
    elif any(k in raw for k in ("自有资金", "专项债", "财政")):
        bits = [k for k in ("自有资金", "专项债", "财政资金", "财政") if k in raw]
        if bits:
            profile.funding_source = "+".join(dict.fromkeys(bits))

    budget = re.search(r"(\d+(?:\.\d+)?)\s*万", raw)
    if budget:
        profile.budget = float(budget.group(1))

    period = re.search(r"(\d+)\s*个?月", raw)
    if period:
        profile.construction_period = int(period.group(1))

    pack = resolve_pack(profile)
    if pack is None:
        for candidate in PACKS:
            if any(a in raw for a in (candidate.name, *candidate.aliases)):
                pack = candidate
                break
    if pack and not profile.industry:
        profile.industry = pack.name
    if pack:
        for scene in pack.scenes:
            if scene in raw and scene not in profile.scenes:
                profile.scenes.append(scene)
        mentioned = [m.id for m in pack.modules if m.title in raw or m.id in raw]
        if mentioned and ("只要" in raw or "模块" in raw or "建设内容" in raw):
            profile.modules = mentioned

    _fill_expected(profile, raw, expecting)
    return profile


def _fill_expected(profile: Profile, raw: str, expecting: str | None) -> None:
    if not expecting or any(k in raw for k in _NOT_A_SLOT) or is_greeting(raw):
        return
    if expecting == "project_name" and not profile.project_name:
        if raw in _INDUSTRY_ONLY or raw.endswith("行业"):
            pack = resolve_pack(Profile(industry=raw, need=raw))
            profile.industry = profile.industry or (pack.name if pack else raw)
            return
        if 4 <= len(raw) <= 40:
            profile.project_name = raw
        return
    if expecting == "place" and not profile.place:
        cleaned = re.sub(r"(属地|在)", "", raw).strip() or raw
        if 2 <= len(re.sub(r"\s", "", cleaned)) <= 12:
            profile.place = cleaned
        return
    if expecting == "construction_unit" and not profile.construction_unit:
        if 2 <= len(raw) <= 40:
            profile.construction_unit = raw
        return
    if expecting == "budget" and profile.budget is None:
        m = re.search(r"(\d+(?:\.\d+)?)", raw)
        if m:
            profile.budget = float(m.group(1))
        return
    if expecting == "construction_period" and profile.construction_period is None:
        m = re.search(r"(\d+)", raw)
        if m:
            profile.construction_period = int(m.group(1))
        return
    if expecting == "compilation_unit" and not profile.compilation_unit:
        if 2 <= len(raw) <= 40:
            profile.compilation_unit = raw
        return
    if expecting == "funding_source" and not profile.funding_source:
        if 2 <= len(raw) <= 40:
            profile.funding_source = raw


def missing_fields(profile: Profile) -> list[str]:
    missing: list[str] = []
    if not (profile.project_name or "").strip():
        missing.append("project_name")
    if not (profile.place or "").strip() or profile.place in {"XX市", "xx市"}:
        missing.append("place")
    if not (profile.construction_unit or "").strip():
        missing.append("construction_unit")
    if profile.budget is None:
        missing.append("budget")
    if profile.construction_period is None:
        missing.append("construction_period")
    return missing


def next_question(profile: Profile) -> str | None:
    miss = missing_fields(profile)
    if not miss:
        return None
    key = miss[0]
    if key == "project_name" and profile.industry:
        return (
            f"行业按「{profile.industry}」记下了。项目全称请写全，"
            f"例如：乐山市{profile.industry}基础设施建设项目。"
        )
    return _QUESTIONS[key]


def is_complete(profile: Profile) -> bool:
    return not missing_fields(profile)


def recap(profile: Profile, job: Job) -> str:
    profile = apply_pack(profile)
    dtype = DOC_TYPE_LABEL.get(job.doc_type, "方案")
    budget = f"{profile.budget:g} 万元" if profile.budget is not None else "—"
    period = f"{profile.construction_period} 个月" if profile.construction_period is not None else "—"
    meta = describe(Job(id="tmp", doc_type=job.doc_type, profile=profile))
    mods = "、".join(m["title"] for m in meta["modules"]) or "（无行业包模块，按需求要点写建设方案）"
    fund = f"资金来源{profile.funding_source}，" if profile.funding_source else ""
    compiler = f"编制单位{profile.compilation_unit}，" if profile.compilation_unit else ""
    pack_line = f"文类「{meta['name']}」"
    if meta["pack"]:
        pack_line += f"，行业包「{meta['pack']}」"
    return (
        f"请确认：为{profile.place}撰写{dtype}《{profile.project_name}》，"
        f"建设单位{profile.construction_unit}，{compiler}总投资{budget}，{fund}建设周期{period}。"
        f"{pack_line}。拟建模块：{mods}。"
        f"回复「确认」开始做目录；有误直接说哪里要改。"
    )
