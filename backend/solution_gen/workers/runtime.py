"""写手：优先 LLM，否则三库接地 stub。禁止 make_lead_agent / task()。"""

from __future__ import annotations

from solution_gen.domain import Chapter, Job
from solution_gen.llm import complete
from solution_gen.rag import canonical_params, canonical_terms
from solution_gen.workers.prose import is_exportable_body


async def grounded_writer(prompt: str, chapter: Chapter, job: Job | None = None) -> str:
    budget = max(2048, min(4096, max(chapter.words // 2, 800)))
    text, tokens = await complete(prompt, max_tokens=budget)
    if is_exportable_body(text):
        chapter.tokens = tokens
        if chapter.diagram and "[DIAGRAM]" not in text and "【图" not in text:
            text += "\n【图占位】[DIAGRAM]\n"
        return text
    return _rag_stub(prompt, chapter, job)


def _rag_stub(prompt: str, chapter: Chapter, job: Job | None) -> str:
    place = ""
    for line in prompt.splitlines():
        if line.startswith("属地:"):
            place = line.split(":", 1)[1].strip()
    terms = canonical_terms()
    params = canonical_params()
    term = "低空智联网" if "低空智联网" in terms else (terms[0] if terms else "统一接入")
    latency = params.get("边缘节点时延", "≤20ms")
    cites = ""
    if job:
        cites = "；".join(f"{c.library}:{c.title}" for c in job.citations[:3])
    loc = place or ""
    return (
        f"{loc}{chapter.title}按产品库口径编制。采用{term}，边缘节点时延 {latency}。"
        f"建设内容与需求分析对应。引用：{cites or '产品库与风格库'}。"
    )
