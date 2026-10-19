from __future__ import annotations

import re


class HtmlDiagramError(ValueError):
    pass


_SVG = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)
_EXT_SCRIPT = re.compile(r"<script\b[^>]*\bsrc\s*=", re.IGNORECASE)


def extract_inline_svg(html: str) -> str:
    raw = html or ""
    if _EXT_SCRIPT.search(raw):
        raise HtmlDiagramError("禁止外链脚本。")
    m = _SVG.search(raw)
    if not m:
        raise HtmlDiagramError("HTML 里没有内联 SVG。")
    return m.group(0)
