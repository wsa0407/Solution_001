from __future__ import annotations

import asyncio

from solution_gen.domain import Chapter, Citation, DocType, Job, JobStatus, Profile
from solution_gen.locale_search import (
    SearchHit,
    fill_locale_search,
    locale_prompt_block,
    matches_place,
    search_locale_policy,
    set_search_provider,
)
from solution_gen.qa.engine import run_qa
from solution_gen.workers.chapter import build_chapter_prompt, generate_chapters


def _qingdao_provider(_query: str) -> list[SearchHit]:
    return [
        SearchHit(
            title="青岛市低空经济发展行动方案",
            excerpt="青岛市加快低空基础设施建设。",
            url="https://example.com/qd",
        ),
        SearchHit(
            title="乐山市低空经济发展规划（2024-2030）",
            excerpt="乐山市以岷江沿线为试点。",
            url="https://example.com/ls",
        ),
    ]


def test_qingdao_search_keeps_place_and_drops_leshan() -> None:
    set_search_provider(_qingdao_provider)
    hits = search_locale_policy(Profile(place="青岛市", industry="低空经济"))
    titles = [c.title for c in hits]
    assert any("青岛" in t for t in titles)
    assert all("乐山" not in t for t in titles)


def test_foreign_hit_rejected() -> None:
    hit = SearchHit(title="乐山市低空经济发展规划（2024-2030）", excerpt="乐山试点")
    assert matches_place(hit, "青岛市") is False
    assert matches_place(hit, "乐山市") is True


def test_empty_search_prompt_forbids_invention() -> None:
    set_search_provider(lambda _q: [])
    ch = Chapter(id="c2", title="项目建设背景及必要性", writing="background", brief="政策")
    job = Job(
        id="t",
        doc_type=DocType.SOLUTION,
        profile=Profile(place="青岛市", industry="低空经济", budget=1, construction_period=12),
        chapters=[ch],
    )
    fill_locale_search(job)
    prompt = build_chapter_prompt(job, ch)
    assert "禁止编造" in prompt
    assert "未见公开专项规划" in prompt


def test_background_prompt_includes_search_title() -> None:
    set_search_provider(_qingdao_provider)
    ch = Chapter(id="c2", title="项目建设背景及必要性", writing="background", brief="政策")
    job = Job(
        id="t",
        doc_type=DocType.SOLUTION,
        profile=Profile(place="青岛市", industry="低空经济", budget=1, construction_period=12),
        chapters=[ch],
    )
    fill_locale_search(job)
    prompt = build_chapter_prompt(job, ch)
    assert "青岛市低空经济发展行动方案" in prompt
    assert "[检索]" in prompt
    assert "乐山市低空经济发展规划" not in prompt


def test_scheme_chapter_skips_locale_block() -> None:
    ch = Chapter(id="c4", title="项目建设方案", writing="scheme", brief="模块")
    job = Job(
        id="t",
        doc_type=DocType.SOLUTION,
        profile=Profile(place="青岛市", industry="低空经济"),
        chapters=[ch],
        citations=[Citation(library="检索", title="青岛市低空经济发展行动方案", why="q")],
    )
    assert locale_prompt_block(job, ch) == ""


def test_generate_chapters_injects_search_into_writer() -> None:
    set_search_provider(_qingdao_provider)
    seen: list[str] = []

    async def writer(prompt: str, _ch: Chapter) -> str:
        seen.append(prompt)
        return "青岛市项目建设背景如下。引用青岛市低空经济发展行动方案。建设内容对应需求。"

    ch = Chapter(id="c2", title="项目建设背景及必要性", writing="background", words=400, brief="政策")
    job = Job(
        id="t",
        doc_type=DocType.SOLUTION,
        status=JobStatus.GENERATING,
        profile=Profile(place="青岛市", industry="低空经济", budget=1, construction_period=12),
        chapters=[ch],
    )
    asyncio.run(generate_chapters(job, writer))
    assert seen and "青岛市低空经济发展行动方案" in seen[0]


def test_qa_flags_vague_policy_without_title() -> None:
    pad = "建设内容。" * 80
    job = Job(
        id="n1",
        doc_type=DocType.SOLUTION,
        status=JobStatus.QA_RUNNING,
        profile=Profile(place="青岛市", industry="低空经济", budget=4000, construction_period=35),
        citations=[
            Citation(library="检索", title="青岛市低空经济发展行动方案", why="q", excerpt="青岛"),
        ],
        chapters=[
            Chapter(
                id="c2",
                title="项目建设背景及必要性",
                writing="background",
                content="青岛市相关规划提出发展低空经济。" + pad,
            )
        ],
    )
    codes = {i.code for i in run_qa(job)}
    assert "LOC-02" in codes


def test_no_deepseek_key_returns_empty(monkeypatch) -> None:
    from solution_gen.config import settings

    set_search_provider(None)
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    hits = search_locale_policy(Profile(place="青岛市", industry="低空经济"))
    assert hits == []


def test_parse_deepseek_response_json() -> None:
    from solution_gen.locale_search import hits_from_deepseek_response

    data = {
        "output": [
            {
                "type": "web_search_call",
                "action": {"type": "search"},
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"results":[{"title":"青岛市低空经济发展行动方案","excerpt":"青岛市加快基建","url":"https://example.com/qd"}]}',
                    }
                ],
            },
        ]
    }
    hits = hits_from_deepseek_response(data)
    assert hits[0].title == "青岛市低空经济发展行动方案"
    assert hits[0].url == "https://example.com/qd"


def test_qa_passes_when_search_title_named() -> None:
    pad = "建设内容。" * 80
    job = Job(
        id="n2",
        doc_type=DocType.SOLUTION,
        status=JobStatus.QA_RUNNING,
        profile=Profile(place="青岛市", industry="低空经济", budget=4000, construction_period=35),
        citations=[
            Citation(library="检索", title="青岛市低空经济发展行动方案", why="q", excerpt="青岛"),
        ],
        chapters=[
            Chapter(
                id="c2",
                title="项目建设背景及必要性",
                writing="background",
                content="依据青岛市低空经济发展行动方案，青岛市推进低空基建。" + pad,
            )
        ],
    )
    assert not any(i.code == "LOC-02" for i in run_qa(job))
