from pathlib import Path


def test_frontend_uses_safe_markdown_renderer():
    root = Path(__file__).resolve().parents[2]
    helper = (root / "static" / "js" / "safe_markdown.js").read_text(encoding="utf-8")
    assert "DOMPurify.sanitize" in helper
    assert "Fail closed" in helper
