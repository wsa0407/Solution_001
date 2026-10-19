from __future__ import annotations

from solution_gen.domain import Chapter, DocType, Profile
from solution_gen.genre import build_outline, contract_for, honors_contract
from solution_gen.llm import complete, parse_json_block


def default_outline(profile: Profile, doc_type: DocType = DocType.SOLUTION) -> list[Chapter]:
    return build_outline(profile, doc_type)


async def llm_outline(profile: Profile, doc_type: DocType) -> list[Chapter] | None:
    contract = contract_for(doc_type)
    titles = "、".join(t.title for t in contract.chapters)
    prompt = (
        f"为「{profile.place}{profile.industry}」生成{contract.name}章节大纲JSON数组。"
        f"需求：{profile.need}。总字数约{profile.words}。"
        f"一级标题必须覆盖文类合同：{titles}。"
        "建设方案按已选模块写 brief，不要改成业务/应用/数据/技术四层。"
        "每项字段: title, words, diagram(bool), brief, writing, depends_on(string array of previous ids like c1)。"
        "只输出JSON。"
    )
    text, _ = await complete(prompt, max_tokens=2000)
    if not text:
        return None
    data = parse_json_block(text)
    if not isinstance(data, list) or len(data) < 3:
        return None
    chapters: list[Chapter] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        cid = f"c{i+1}"
        chapters.append(
            Chapter(
                id=cid,
                title=str(item.get("title") or f"第{i+1}章"),
                words=int(item.get("words") or 6000),
                diagram=bool(item.get("diagram")),
                brief=str(item.get("brief") or ""),
                writing=str(item.get("writing") or ""),
                depends_on=list(item.get("depends_on") or ([f"c{i}"] if i else [])),
            )
        )
    if not honors_contract(chapters, profile, doc_type):
        return None
    return chapters or None
