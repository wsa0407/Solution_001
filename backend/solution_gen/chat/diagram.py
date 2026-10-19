from __future__ import annotations

import re

from solution_gen.domain import DiagramKind, Job

KIND_LABEL = {
    DiagramKind.ARCHITECTURE: "架构图",
    DiagramKind.FLOWCHART: "流程图",
    DiagramKind.GANTT: "甘特图",
}

_EMIT = ("按这些出图", "按这个出图", "开始出图", "就这些出图", "就这些")
_DEFAULT_TITLE = {
    DiagramKind.ARCHITECTURE: ("总体架构", "建设方案", "总体方案", "核心建设内容", "项目建设方案"),
    DiagramKind.FLOWCHART: ("需求分析", "核心建设内容", "建设方案", "总体架构", "项目需求分析"),
    DiagramKind.GANTT: ("实施计划", "进度与投资", "投资估算", "项目实施计划"),
}
_CN_NUM = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def wants_emit(text: str) -> bool:
    return any(k in (text or "") for k in _EMIT)


def label_of(kind: DiagramKind) -> str:
    return KIND_LABEL.get(kind, str(kind))


def resolve_chapter(job: Job, text: str, kind: DiagramKind) -> str:
    for c in job.chapters:
        if c.title and c.title in (text or ""):
            return c.id
    m = re.search(r"第\s*(\d+)\s*章", text or "")
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(job.chapters):
            return job.chapters[idx].id
    m = re.search(r"第\s*([一二三四五六七八九十])\s*章", text or "")
    if m:
        idx = _CN_NUM.get(m.group(1), 0) - 1
        if 0 <= idx < len(job.chapters):
            return job.chapters[idx].id
    for title in _DEFAULT_TITLE.get(kind, ()):
        hit = next((c.id for c in job.chapters if c.title == title), None)
        if hit:
            return hit
    return job.chapters[0].id if job.chapters else ""
