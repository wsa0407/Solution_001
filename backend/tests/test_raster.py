from pathlib import Path

from solution_gen.skills.raster import svg_to_png


def test_svg_to_png_writes_png_magic(tmp_path: Path) -> None:
    dest = tmp_path / "out.png"
    svg_to_png(
        "<svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'><rect width='8' height='8' fill='#000'/></svg>",
        dest,
    )
    assert dest.exists()
    assert dest.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
