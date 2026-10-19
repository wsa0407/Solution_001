from __future__ import annotations

from solution_gen.domain import DocType, Profile
from solution_gen.genre import apply_pack, build_outline, closer_sentence, contract_for, resolve_pack
from solution_gen.workers.chapter import build_chapter_prompt
from solution_gen.workers.outline import default_outline
from solution_gen.domain import Chapter, Job


def test_proposal_outline_follows_genre_not_it_template() -> None:
    profile = apply_pack(
        Profile(place="乐山市", industry="低空经济", need="示范", budget=50000, construction_period=24)
    )
    titles = [c.title for c in default_outline(profile, DocType.SOLUTION)]
    joined = " ".join(titles)
    assert "项目建设方案" in joined
    assert "概述" in joined
    assert "主要结论和建议" in joined
    assert "总体架构" not in joined
    assert "核心建设内容" not in joined
    scheme = next(c for c in default_outline(profile, DocType.SOLUTION) if c.title == "项目建设方案")
    assert "低空智联网设施" in scheme.brief
    assert "业务 / 应用 / 数据 / 技术" in scheme.brief  # prohibition, not the old chapter structure


def test_unknown_industry_keeps_genre_without_pack_modules() -> None:
    profile = Profile(place="乐山市", industry="水利", need="供水厂扩建")
    assert resolve_pack(profile) is None
    titles = [c.title for c in build_outline(profile, DocType.SOLUTION)]
    joined = " ".join(titles)
    assert "项目建设方案" in joined
    assert "低空智联网" not in joined
    assert "环保" not in joined  # no civil modules selected


def test_civil_module_turns_on_ehs_chapter() -> None:
    profile = apply_pack(Profile(place="乐山市", industry="低空经济", modules=["ops_center"]))
    titles = [c.title for c in build_outline(profile, DocType.SOLUTION)]
    assert any("环保" in t for t in titles)
    assert "1套运营服务保障体系" in closer_sentence(profile)


def test_feasibility_contract_still_has_economy() -> None:
    contract = contract_for(DocType.FEASIBILITY)
    titles = [c.title for c in contract.chapters]
    assert "经济评价" in titles
    assert "多方案比选" in titles


def test_chapter_prompt_is_genre_not_latency_slogan() -> None:
    profile = apply_pack(Profile(place="乐山市", industry="低空经济", budget=1, construction_period=12))
    ch = Chapter(id="c1", title="概述", words=1000, writing="overview", brief="收口")
    job = Job(id="t", doc_type=DocType.SOLUTION, profile=profile, chapters=[ch])
    prompt = build_chapter_prompt(job, ch)
    assert "固定资产投资" in prompt
    assert "≤20ms" not in prompt
    assert "四层" in prompt  # as a prohibition
    assert "第1章" in prompt or "第一章" in prompt
    assert "1.1" in prompt
