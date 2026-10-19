#!/usr/bin/env python3
"""Render a diagram JSON spec into an HTML file and optionally a PNG image.

Usage:
    generate_architecture.py --json <spec.json> -o <out.html> [--png <out.png>]

Supports kinds: architecture (总体框架图), flowchart (流程图), gantt (甘特图).
The PNG is drawn with Pillow so it can be embedded into Word documents.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# --------------------------------------------------------------------------
# SVG generation (kept in sync with solution_gen/skills/charts.py)
# --------------------------------------------------------------------------

def svg_architecture(spec: dict) -> str:
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
        name = _esc(str(layer.get("name") or f"L{i + 1}"))
        items = "、".join(str(x) for x in (layer.get("items") or []))
        parts.append(f'<rect x="20" y="{y}" width="{w - 40}" height="{box_h}" rx="4" fill="#fff" stroke="{color}"/>')
        parts.append(f'<text x="36" y="{y + 22}" font-size="13" font-weight="600" fill="{color}">{name}</text>')
        parts.append(f'<text x="36" y="{y + 40}" font-size="12" fill="#1a1612">{_esc(items)}</text>')
        y += box_h + gap
    parts.append("</svg>")
    return "".join(parts)


def svg_flowchart(spec: dict) -> str:
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
        parts.append(
            f'<text x="{x + box_w / 2}" y="{y + 27}" text-anchor="middle" font-size="12" fill="#1a1612">{_esc(str(step))}</text>'
        )
        if i < n - 1:
            x2 = x + box_w + 6
            parts.append(
                f'<line x1="{x + box_w}" y1="{y + 22}" x2="{x2 + 16}" y2="{y + 22}" stroke="#8c3a1e" marker-end="url(#a)"/>'
            )
        x += box_w + 28
    parts.append(
        '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">'
        '<path d="M0,0 L8,4 L0,8 z" fill="#8c3a1e"/></marker></defs>'
    )
    parts.append("</svg>")
    return "".join(parts)


def svg_gantt(spec: dict) -> str:
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
        name = _esc(str(item.get("name") or f"任务{i + 1}"))
        start = float(item.get("start") or 0)
        end = float(item.get("end") or start + 1)
        x = left + inner_w * start / months
        bw = max(8, inner_w * max(end - start, 0.5) / months)
        parts.append(f'<text x="20" y="{y + 16}" font-size="12" fill="#1a1612">{name}</text>')
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bar_h}" rx="3" fill="#2c5f4a"/>')
    parts.append("</svg>")
    return "".join(parts)


def render_svg(spec: dict) -> str:
    kind = spec.get("kind")
    if kind == "flowchart":
        return svg_flowchart(spec)
    if kind == "gantt":
        return svg_gantt(spec)
    return svg_architecture(spec)


# --------------------------------------------------------------------------
# PNG rendering with Pillow (mirrors the SVG layouts above)
# --------------------------------------------------------------------------

def _hex_to_rgb(value: str, default: tuple[int, int, int] = (26, 22, 18)) -> tuple[int, int, int]:
    v = (value or "").lstrip("#")
    if len(v) != 6:
        return default
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return default


def png_architecture(spec: dict) -> Image.Image:
    w, h = int(spec.get("width") or 640), int(spec.get("height") or 360)
    layers = spec.get("layers") or []
    title = str(spec.get("title") or "架构图")
    gap = 12
    top = 44
    box_h = max(44, int((h - top - 24 - gap * max(len(layers) - 1, 0)) / max(len(layers), 1)))
    img = Image.new("RGB", (w, h), (251, 248, 241))
    draw = ImageDraw.Draw(img)
    f_title = load_font(16)
    f_name = load_font(13)
    f_items = load_font(12)
    draw.text((24, 10), title, font=f_title, fill=(26, 22, 18))
    colors = ["#8c3a1e", "#2c5f4a", "#a15c12", "#3a5f7a", "#5c4a7a"]
    y = top
    for i, layer in enumerate(layers):
        color = _hex_to_rgb(colors[i % len(colors)])
        name = str(layer.get("name") or f"L{i + 1}")
        items = "、".join(str(x) for x in (layer.get("items") or []))
        draw.rounded_rectangle((20, y, w - 20, y + box_h), radius=4, fill=(255, 255, 255), outline=color, width=1)
        draw.text((36, y + 8), name, font=f_name, fill=color)
        draw.text((36, y + 28), items, font=f_items, fill=(26, 22, 18))
        y += box_h + gap
    return img


def png_flowchart(spec: dict) -> Image.Image:
    w, h = int(spec.get("width") or 640), int(spec.get("height") or 180)
    steps = spec.get("steps") or ["开始", "结束"]
    title = str(spec.get("title") or "流程图")
    n = len(steps)
    box_w = min(110, int((w - 40 - (n - 1) * 28) / max(n, 1)))
    y = 80
    img = Image.new("RGB", (w, h), (251, 248, 241))
    draw = ImageDraw.Draw(img)
    f_title = load_font(16)
    f_step = load_font(12)
    color = _hex_to_rgb("#8c3a1e")
    draw.text((24, 10), title, font=f_title, fill=(26, 22, 18))
    x = 20
    for i, step in enumerate(steps):
        draw.rounded_rectangle((x, y, x + box_w, y + 44), radius=4, fill=(255, 255, 255), outline=color, width=1)
        text = str(step)
        box = draw.textbbox((0, 0), text, font=f_step)
        tw = box[2] - box[0]
        draw.text((x + (box_w - tw) / 2, y + 14), text, font=f_step, fill=(26, 22, 18))
        if i < n - 1:
            x2 = x + box_w + 6
            draw.line((x + box_w, y + 22, x2 + 16, y + 22), fill=color, width=1)
            draw.polygon([(x2 + 16, y + 16), (x2 + 22, y + 22), (x2 + 16, y + 28)], fill=color)
        x += box_w + 28
    return img


def png_gantt(spec: dict) -> Image.Image:
    w, h = int(spec.get("width") or 640), int(spec.get("height") or 200)
    items = spec.get("items") or []
    months = max(int(spec.get("months") or 12), 1)
    title = str(spec.get("title") or "甘特图")
    left = 120
    top = 56
    bar_h = 22
    inner_w = w - left - 24
    img = Image.new("RGB", (w, h), (251, 248, 241))
    draw = ImageDraw.Draw(img)
    f_title = load_font(16)
    f_name = load_font(12)
    bar_color = _hex_to_rgb("#2c5f4a")
    draw.text((24, 10), title, font=f_title, fill=(26, 22, 18))
    for i, item in enumerate(items):
        y = top + i * 36
        name = str(item.get("name") or f"任务{i + 1}")
        start = float(item.get("start") or 0)
        end = float(item.get("end") or start + 1)
        x = left + inner_w * start / months
        bw = max(8, inner_w * max(end - start, 0.5) / months)
        draw.text((20, y), name, font=f_name, fill=(26, 22, 18))
        draw.rounded_rectangle((x, y, x + bw, y + bar_h), radius=3, fill=bar_color)
    return img


def render_png(spec: dict) -> Image.Image:
    kind = spec.get("kind")
    if kind == "flowchart":
        return png_flowchart(spec)
    if kind == "gantt":
        return png_gantt(spec)
    return png_architecture(spec)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render diagram JSON to HTML and PNG.")
    parser.add_argument("--json", required=True, help="path to diagram spec JSON")
    parser.add_argument("-o", required=True, dest="out", help="output HTML path")
    parser.add_argument("--png", default=None, help="optional output PNG path")
    args = parser.parse_args()

    spec = json.loads(Path(args.json).read_text(encoding="utf-8"))
    svg = render_svg(spec)

    html_name = Path(args.out).name
    png_name = Path(args.png).name if args.png else None
    if png_name:
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{_esc(str(spec.get('title') or '图'))}</title></head>"
            f"<body style='margin:0'><img src='{png_name}' style='max-width:100%'></body></html>"
        )
    else:
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{_esc(str(spec.get('title') or '图'))}</title></head>"
            f"<body>{svg}</body></html>"
        )
    Path(args.out).write_text(html, encoding="utf-8")

    if args.png:
        render_png(spec).save(args.png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
