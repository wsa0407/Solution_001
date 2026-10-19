from __future__ import annotations

from pathlib import Path


def svg_to_png(svg: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = (svg or "").encode("utf-8")
    try:
        import cairosvg

        cairosvg.svg2png(bytestring=raw, write_to=str(dest))
        if dest.exists() and dest.stat().st_size > 0:
            return
    except Exception:
        pass
    _pymupdf_svg_to_png(raw, dest)


def _pymupdf_svg_to_png(raw: bytes, dest: Path) -> None:
    import pymupdf

    doc = pymupdf.open(stream=raw, filetype="svg")
    try:
        page = doc[0]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        dest.write_bytes(pix.tobytes("png"))
    finally:
        doc.close()
