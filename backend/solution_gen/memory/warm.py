from __future__ import annotations

from solution_gen.domain import Job, Profile, WarmMemory
from solution_gen.genre.packs import apply_pack, resolve_pack


def seed_warm(profile: Profile) -> WarmMemory:
    """生成开始后写入温记忆。术语来自行业包，不在这里写死某个行业。"""
    profile = apply_pack(profile)
    terms = [profile.industry] if profile.industry else []
    pack = resolve_pack(profile)
    if pack:
        terms.extend(pack.terms)
    data = [f"目标体量 {profile.words:,} 字", f"属地 {profile.place}"]
    if profile.budget is not None:
        data.append(f"总投资 {profile.budget:g} 万元")
    return WarmMemory(terms=list(dict.fromkeys(t for t in terms if t)), data=data)


def upsert_term(job: Job, term: str) -> None:
    if term and term not in job.warm.terms:
        job.warm.terms.append(term)


def upsert_datum(job: Job, datum: str) -> None:
    if datum and datum not in job.warm.data:
        job.warm.data.append(datum)
