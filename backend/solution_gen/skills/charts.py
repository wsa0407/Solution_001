from __future__ import annotations

import base64
from pathlib import Path

from solution_gen.config import settings
from solution_gen.domain import DiagramKind, DiagramRequest, Job


def default_architecture(title: str, place: str) -> dict:
    return {
        "kind": DiagramKind.ARCHITECTURE.value,
        "title": f"{place}{title}",
        "layers": [
            {"name": "用户层", "items": ["政务用户", "运营单位", "公众服务"]},
            {"name": "应用层", "items": ["飞行服务", "场景运营", "指挥调度"]},
            {"name": "支撑层", "items": ["低空中台", "统一接入"]},
            {"name": "数据层", "items": ["时空基准", "低空数据归集"]},
            {"name": "基础设施层", "items": ["低空智联网", "边缘节点≤20ms"]},
        ],
        "pillars": ["标准", "安全", "运维"],
        "width": 640,
        "height": 360,
    }


def default_flowchart(title: str, place: str) -> dict:
    return {
        "kind": DiagramKind.FLOWCHART.value,
        "title": f"{place}{title}流程",
        "steps": ["需求确认", "方案设计", "建设实施", "联调验收", "运营保障"],
        "width": 640,
        "height": 180,
    }


def default_gantt(title: str, place: str, months: int = 24) -> dict:
    span = max(12, months)
    return {
        "kind": DiagramKind.GANTT.value,
        "title": f"{place}{title}进度",
        "items": [
            {"name": "前期准备", "start": 0, "end": max(2, span // 8)},
            {"name": "主体建设", "start": max(1, span // 8), "end": max(8, span * 3 // 4)},
            {"name": "联调验收", "start": max(6, span * 2 // 3), "end": span},
        ],
        "months": span,
        "width": 640,
        "height": 200,
    }


def spec_from_request(job: Job, req: DiagramRequest) -> dict:
    return attach_image(build_spec(job, req))


def build_spec(job: Job, req: DiagramRequest) -> dict:
    place = job.profile.place if job.profile else ""
    ch = next((c for c in job.chapters if c.id == req.chapter_id), None)
    title = ch.title if ch else "方案"
    if req.kind is DiagramKind.FLOWCHART:
        spec = default_flowchart(title, place)
    elif req.kind is DiagramKind.GANTT:
        months = job.profile.construction_period if job.profile and job.profile.construction_period else 24
        spec = default_gantt(title, place, months)
    else:
        spec = default_architecture(title, place)
    if req.reference and "按正文" not in req.reference:
        spec["reference"] = req.reference
        if req.kind is DiagramKind.FLOWCHART and "→" in req.reference:
            spec["steps"] = [p.strip() for p in req.reference.split("→") if p.strip()][:8]
    spec["chapter_id"] = req.chapter_id
    spec["placement"] = req.placement
    return spec


def attach_image(spec: dict) -> dict:
    out = dict(spec)
    out["image_data"] = svg_data_uri(render_svg(out))
    return out


async def enrich_spec(spec: dict, job: Job, req: DiagramRequest) -> dict:
    """可用写手补结构；失败则保留默认 spec。渲染仍走本函数之外的 charts SVG。"""
    from solution_gen.llm import complete, parse_json_block

    if not settings.deepseek_api_key:
        return spec
    ch = next((c for c in job.chapters if c.id == req.chapter_id), None)
    excerpt = ((ch.content or "")[:400] if ch else "")
    prompt = (
        "只输出一段 JSON，不要解释，不要改任务状态。\n"
        f"图类型: {req.kind.value}\n"
        f"章节: {ch.title if ch else ''}\n"
        f"位置: {req.placement}\n"
        f"参考: {req.reference or '按正文生成'}\n"
        f"正文摘录: {excerpt}\n"
        "架构图用 layers:[{name, items:[]}]; 流程图用 steps:[字符串]; "
        "甘特图用 months:int 与 items:[{name, start, end}]，start/end 为月份序号。\n"
    )
    text, _ = await complete(prompt, max_tokens=800)
    data = parse_json_block(text or "")
    if not isinstance(data, dict):
        return spec
    merged = dict(spec)
    if isinstance(data.get("layers"), list) and data["layers"]:
        merged["layers"] = data["layers"]
    if isinstance(data.get("steps"), list) and data["steps"]:
        merged["steps"] = [str(x) for x in data["steps"] if str(x).strip()][:8]
    if isinstance(data.get("items"), list) and data["items"]:
        merged["items"] = data["items"]
    if data.get("title"):
        merged["title"] = str(data["title"])
    if data.get("months"):
        try:
            merged["months"] = int(data["months"])
        except (TypeError, ValueError):
            pass
    return merged


def render_svg(spec: dict) -> str:
    kind = spec.get("kind")
    if kind == DiagramKind.FLOWCHART.value:
        return _svg_flowchart(spec)
    if kind == DiagramKind.GANTT.value:
        return _svg_gantt(spec)
    return _svg_architecture(spec)


def svg_data_uri(svg: str) -> str:
    raw = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{raw}"


def render_architecture_json(json_path: Path, html_out: Path, png_out: Path | None = None) -> bool:
    scripts = settings.diagram_skill_scripts
    generator = scripts / "generate_architecture.py"
    if not generator.exists():
        html_out.write_text(f"<pre>{json_path.read_text(encoding='utf-8')}</pre>", encoding="utf-8")
        return False
    import subprocess
    import sys

    cmd = [sys.executable, str(generator), "--json", str(json_path), "-o", str(html_out)]
    if png_out:
        cmd.extend(["--png", str(png_out)])
    try:
        subprocess.run(cmd, check=True, timeout=60)
        return True
    except Exception:
        html_out.write_text(f"<pre>{json_path.read_text(encoding='utf-8')}</pre>", encoding="utf-8")
        return False


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _svg_architecture(spec: dict) -> str:
    w, h = int(spec.get("width") or 640), int(spec.get("height") or 360)
    layers = spec.get("layers") or []
    title = _esc(str(spec.get("title") or "架构图"))
    gap = 12
    top = 44
    box_h = max(44, int((h - top - 24 - gap * max(len(layers) - 1, 0)) / max(len(layers), 1)))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#fbf8f1"/>',
        f'<text x="24" y="28" font-size="16" font-weight="700" fill="#1a1612">{title}</text>',
    ]
    y = top
    colors = ["#8c3a1e", "#2c5f4a", "#a15c12", "#3a5f7a", "#5c4a7a"]
    for i, layer in enumerate(layers):
        color = colors[i % len(colors)]
        name = _esc(str(layer.get("name") or f"L{i+1}"))
        items = "、".join(str(x) for x in (layer.get("items") or []))
        parts.append(f'<rect x="20" y="{y}" width="{w-40}" height="{box_h}" rx="4" fill="#fff" stroke="{color}"/>')
        parts.append(f'<text x="36" y="{y + 22}" font-size="13" font-weight="600" fill="{color}">{name}</text>')
        parts.append(f'<text x="36" y="{y + 40}" font-size="12" fill="#1a1612">{_esc(items)}</text>')
        y += box_h + gap
    parts.append("</svg>")
    return "".join(parts)


def _svg_flowchart(spec: dict) -> str:
    w, h = int(spec.get("width") or 640), int(spec.get("height") or 180)
    steps = spec.get("steps") or ["开始", "结束"]
    title = _esc(str(spec.get("title") or "流程图"))
    n = len(steps)
    box_w = min(110, int((w - 40 - (n - 1) * 28) / max(n, 1)))
    y = 80
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#fbf8f1"/>',
        f'<text x="24" y="28" font-size="16" font-weight="700" fill="#1a1612">{title}</text>',
    ]
    x = 20
    for i, step in enumerate(steps):
        parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="44" rx="4" fill="#fff" stroke="#8c3a1e"/>')
        parts.append(f'<text x="{x + box_w / 2}" y="{y + 27}" text-anchor="middle" font-size="12" fill="#1a1612">{_esc(str(step))}</text>')
        if i < n - 1:
            x2 = x + box_w + 6
            parts.append(f'<line x1="{x + box_w}" y1="{y + 22}" x2="{x2 + 16}" y2="{y + 22}" stroke="#8c3a1e" marker-end="url(#a)"/>')
        x += box_w + 28
    parts.append('<defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#8c3a1e"/></marker></defs>')
    parts.append("</svg>")
    return "".join(parts)


def _svg_gantt(spec: dict) -> str:
    w, h = int(spec.get("width") or 640), int(spec.get("height") or 200)
    items = spec.get("items") or []
    months = max(int(spec.get("months") or 12), 1)
    title = _esc(str(spec.get("title") or "甘特图"))
    left = 120
    top = 56
    bar_h = 22
    inner_w = w - left - 24
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#fbf8f1"/>',
        f'<text x="24" y="28" font-size="16" font-weight="700" fill="#1a1612">{title}</text>',
    ]
    for i, item in enumerate(items):
        y = top + i * 36
        name = _esc(str(item.get("name") or f"任务{i+1}"))
        start = float(item.get("start") or 0)
        end = float(item.get("end") or start + 1)
        x = left + inner_w * start / months
        bw = max(8, inner_w * max(end - start, 0.5) / months)
        parts.append(f'<text x="20" y="{y + 16}" font-size="12" fill="#1a1612">{name}</text>')
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bar_h}" rx="3" fill="#2c5f4a"/>')
    parts.append("</svg>")
    return "".join(parts)
