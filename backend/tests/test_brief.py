from __future__ import annotations

from solution_gen.chat.brief import is_complete, merge_from_text, missing_fields, next_question, recap
from solution_gen.domain import DocType, Job, Profile


def test_only_ask_for_proposal_is_incomplete() -> None:
    p = merge_from_text(Profile(), "帮我写一份项目建议书")
    assert not is_complete(p)
    assert "place" in missing_fields(p)
    assert next_question(p)


def test_fill_then_recap_contains_place_and_budget() -> None:
    p = Profile()
    p = merge_from_text(p, "帮我写一份项目建议书")
    p = merge_from_text(p, "项目名称乐山市低空经济基础设施建设项目")
    p = merge_from_text(p, "属地在乐山市，建设单位乐山低空科技有限公司，总投资 50000 万元，周期 24 个月")
    assert is_complete(p)
    assert p.place == "乐山市"
    assert p.budget == 50000
    assert p.construction_period == 24
    job = Job(id="j1", doc_type=DocType.SOLUTION)
    text = recap(p, job)
    assert "乐山" in text
    assert "50000" in text
    assert next_question(p) is None


def test_industry_reply_does_not_loop_same_name_question() -> None:
    p = merge_from_text(Profile(), "帮我写一份项目建议书")
    assert next_question(p) == "项目全称是什么？"
    p = merge_from_text(p, "低空经济", expecting="project_name")
    assert not p.project_name
    assert p.industry == "低空经济"
    q = next_question(p)
    assert q and "写全" in q
    assert "项目全称是什么？" != q
    p = merge_from_text(p, "乐山市低空经济基础设施建设项目", expecting="project_name")
    assert p.project_name == "乐山市低空经济基础设施建设项目"
    assert p.place == "乐山市"
    assert next_question(p) == "建设单位是哪家？"


def test_plain_answer_fills_current_slot() -> None:
    p = merge_from_text(Profile(), "帮我写一份项目建议书")
    p = merge_from_text(p, "乐山市低空经济基础设施建设项目", expecting="project_name")
    p = merge_from_text(p, "乐山市", expecting="place")
    p = merge_from_text(p, "乐山低空科技有限公司", expecting="construction_unit")
    p = merge_from_text(p, "50000", expecting="budget")
    p = merge_from_text(p, "24", expecting="construction_period")
    assert is_complete(p)
    assert p.budget == 50000
    assert p.construction_period == 24


def test_never_defaults_xx_city() -> None:
    p = merge_from_text(Profile(), "帮我写一份项目建议书")
    assert p.place != "XX市"
    assert "place" in missing_fields(p)
