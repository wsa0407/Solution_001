from solution_gen.skills.svghtml import extract_inline_svg, HtmlDiagramError


def test_extract_first_svg() -> None:
    html = "<!doctype html><html><body><svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'><rect width='8' height='8'/></svg></body></html>"
    svg = extract_inline_svg(html)
    assert "<svg" in svg
    assert "rect" in svg


def test_reject_external_script() -> None:
    html = "<html><script src='https://evil.example/x.js'></script><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    try:
        extract_inline_svg(html)
        raise AssertionError("should reject")
    except HtmlDiagramError as exc:
        assert "脚本" in str(exc) or "script" in str(exc).lower()


def test_missing_svg_fails() -> None:
    try:
        extract_inline_svg("<html><body>no figure</body></html>")
        raise AssertionError("should reject")
    except HtmlDiagramError:
        pass
