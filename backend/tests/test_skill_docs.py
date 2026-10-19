from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "dsh-profile" / "skills"
AGENTS = ROOT / "dsh-profile" / "agents"
PLUGIN = ROOT / "dsh-profile" / "src" / "plugin.ts"
FORBIDDEN = ("load_skill", "delegate_agent")


def _assert_skip_qa_is_prohibition_only(text: str) -> None:
    """skip-qa may appear as a ban, never as an action to call."""
    lowered = text.lower()
    if "skip-qa" not in lowered:
        return
    assert "action: skip-qa" not in lowered
    assert re.search(r"action\s*[:=]\s*skip-qa", lowered) is None
    for match in re.finditer(r"skip-qa", text, flags=re.IGNORECASE):
        start = max(0, match.start() - 16)
        end = min(len(text), match.end() + 16)
        window = text[start:end]
        assert any(tok in window for tok in ("不要", "没有", "禁止")), window


def test_skill_inventory_and_two_subagents_exist() -> None:
    for name in (
        "collect-brief",
        "draft-outline",
        "write-chapters",
        "emit-diagrams",
        "polish-deliver",
    ):
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "skill" in text
        assert "solution_skill" in text
        for bad in FORBIDDEN:
            assert bad not in text
        assert "skip-qa" in text.lower() or "solution_skill" in text

    diagram_path = SKILLS / "diagram-design" / "SKILL.md"
    assert diagram_path.is_file()
    diagram = diagram_path.read_text(encoding="utf-8")
    assert "name: diagram-design" in diagram
    for bad in FORBIDDEN:
        assert bad not in diagram
    _assert_skip_qa_is_prohibition_only(diagram)
    assert "attach-diagram" in diagram
    assert "template.html" in diagram
    assert "Mandatory connector" in diagram
    assert "onboarding.md" not in diagram
    assets = SKILLS / "diagram-design" / "assets"
    for name in ("template.html", "example-architecture.html", "example-flowchart.html", "example-gantt.html"):
        assert (assets / name).is_file(), name

    emit = (SKILLS / "emit-diagrams" / "SKILL.md").read_text(encoding="utf-8")
    assert "draft-diagram-spec" in emit
    assert "confirm-diagram-spec" in emit
    assert "attach-diagram" in emit
    assert "确认" in emit

    write = (SKILLS / "write-chapters" / "SKILL.md").read_text(encoding="utf-8")
    assert "不要自己搜网写正文" in write

    proposal = (AGENTS / "proposal.md").read_text(encoding="utf-8")
    feasibility = (AGENTS / "feasibility.md").read_text(encoding="utf-8")
    main = (AGENTS / "main.md").read_text(encoding="utf-8")
    for text in (proposal, feasibility, main):
        for bad in FORBIDDEN:
            assert bad not in text
        assert "skill" in text
        assert "solution_skill" in text
    assert "collect-brief" in proposal and "polish-deliver" in proposal
    assert "固定资产投资" in proposal
    assert "genre" in proposal.lower() or "行业包" in proposal
    assert "智联网" not in proposal
    assert "四层" not in proposal
    assert "固定资产投资" in feasibility or "文类" in feasibility
    assert "collect-brief" in feasibility
    assert "不要自己搜网写正文" in proposal
    assert "不要自己搜网写正文" in feasibility
    assert "diagram-design" in proposal or "文字说明" in proposal
    assert "diagram-design" in feasibility or "文字说明" in feasibility
    assert "只路由" in main or "路由" in main
    assert "可研" in main
    assert "subagent" in main.lower() or "子 agent" in main
    assert "五份说明书" not in main
    assert "diagram-design" in main

    plugin = PLUGIN.read_text(encoding="utf-8")
    assert "draft-diagram-spec" in plugin
    assert "attach-diagram" in plugin

    notice = (SKILLS / "diagram-design" / "NOTICE").read_text(encoding="utf-8")
    assert "cathrynlavery/diagram-design" in notice


def test_plugin_registers_solution_skill_only() -> None:
    text = PLUGIN.read_text(encoding="utf-8")
    assert "inject = ['tools']" in text or 'inject = ["tools"]' in text
    assert "defineTool" in text
    assert "solution_skill" in text
    assert "systemPrompt" not in text
    assert "proposal.md" not in text
    assert "feasibility.md" not in text
    assert "load_skill" not in text
    assert "delegate_agent" not in text
