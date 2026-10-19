from __future__ import annotations

from solution_gen.domain import Chapter, DocType, Job, JobStatus, Profile
from solution_gen.qa.engine import run_qa
from solution_gen.skills.document import export_docx
from solution_gen.workers.chapter import build_chapter_prompt
from solution_gen.workers.numbering import (
    chinese_chapter_num,
    normalize_chapter_numbering,
    numbering_issues,
    parse_chinese_int,
)


def test_chinese_chapter_ordinals() -> None:
    assert [chinese_chapter_num(i) for i in range(1, 13)] == [
        "一",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
    ]
    assert parse_chinese_int("十二") == 12
    assert parse_chinese_int("7") == 7


def test_rewrites_wrong_chapter_and_subsection_heads() -> None:
    raw = (
        "# 第一章 项目建设背景及必要性\n\n"
        "## 1.1 建设背景\n\n"
        "### 1.1.1 国家政策背景\n\n"
        "政策如下。\n"
    )
    out = normalize_chapter_numbering(raw, 2, "项目建设背景及必要性")
    assert "第一章" not in out
    assert "项目建设背景及必要性" not in out.splitlines()[0]
    assert "## 2.1 建设背景" in out
    assert "### 2.1.1 国家政策背景" in out


def test_implementation_plan_is_chapter_seven() -> None:
    raw = (
        "## 第六章 项目实施计划\n\n"
        "建设周期为35个月。\n\n"
        "### 6.1 实施原则与总体思路\n\n"
        "项目总体实施架构如图6-1所示。\n"
    )
    out = normalize_chapter_numbering(raw, 7, "项目实施计划")
    assert "第六章" not in out
    assert "### 7.1 实施原则与总体思路" in out
    assert "如图7-1所示" in out
    assert numbering_issues(out, 7, "项目实施计划", "c7") == []


def test_conclusion_is_chapter_eleven_not_twelve() -> None:
    raw = "## 第十二章 主要结论和建议\n\n### 12.1 主要结论\n\n收口如下。\n"
    out = normalize_chapter_numbering(raw, 11, "主要结论和建议")
    assert "第十二章" not in out
    assert "### 11.1 主要结论" in out


def test_does_not_rewrite_money_or_version_numbers() -> None:
    raw = (
        "## 第七章 项目投融资与财务方案\n\n"
        "### 7.1 编制依据\n\n"
        "白皮书 V2.1 与预备费 8.25 万元。\n"
        "8.25 万元为预备费。\n"
    )
    out = normalize_chapter_numbering(raw, 8, "项目投融资与财务方案")
    assert "8.25 万元" in out
    assert "V2.1" in out
    assert "### 8.1 编制依据" in out


def test_risk_chapter_without_ordinal_drops_duplicate_title() -> None:
    raw = "## 项目风险管控方案\n\n工程风险如下。\n"
    out = normalize_chapter_numbering(raw, 10, "项目风险管控方案")
    assert out.strip().startswith("工程风险")


def test_qa_flags_mismatched_numbering() -> None:
    job = Job(
        id="n1",
        doc_type=DocType.SOLUTION,
        status=JobStatus.QA_RUNNING,
        profile=Profile(place="青岛市", industry="低空经济", budget=4000, construction_period=35),
        chapters=[
            Chapter(id="c1", title="概述", writing="overview", content="概述。青岛市。" + "建设内容。" * 80),
            Chapter(
                id="c2",
                title="项目建设背景及必要性",
                writing="background",
                content="# 第一章 项目建设背景及必要性\n\n## 1.1 建设背景\n\n青岛市政策。" + "建设内容。" * 80,
            ),
        ],
    )
    codes = {i.code for i in run_qa(job)}
    assert "CH-NUM-01" in codes or "CH-NUM-02" in codes


def test_prompt_binds_chapter_to_outline_index() -> None:
    ch1 = Chapter(id="c1", title="概述", words=1000, writing="overview", brief="收口")
    ch2 = Chapter(id="c2", title="项目建设背景及必要性", words=1000, writing="background", brief="政策")
    job = Job(
        id="t",
        doc_type=DocType.SOLUTION,
        profile=Profile(place="乐山市", industry="低空经济", budget=1, construction_period=12),
        chapters=[ch1, ch2],
    )
    prompt = build_chapter_prompt(job, ch2)
    assert "第2章" in prompt or "第二章" in prompt
    assert "2.1" in prompt
    assert "1. 概述" in prompt
    assert "2. 项目建设背景及必要性" in prompt


def test_export_docx_uses_outline_index_not_model_heading(tmp_path) -> None:
    job = Job(
        id="nexp",
        doc_type=DocType.SOLUTION,
        status=JobStatus.DELIVERED,
        profile=Profile(place="青岛", industry="低空经济", project_name="青岛项目"),
        chapters=[
            Chapter(id="c1", title="概述", content="### 1.1 项目名称\n\n青岛项目。"),
            Chapter(
                id="c2",
                title="项目建设背景及必要性",
                content="# 第一章 项目建设背景及必要性\n\n## 1.1 建设背景\n\n政策如下。",
            ),
        ],
    )
    path = tmp_path / "out.docx"
    export_docx(job, path)
    from docx import Document

    texts = [p.text for p in Document(str(path)).paragraphs]
    blob = "\n".join(texts)
    assert "2. 项目建设背景及必要性" in blob
    assert "第一章" not in blob
    assert "2.1 建设背景" in blob
