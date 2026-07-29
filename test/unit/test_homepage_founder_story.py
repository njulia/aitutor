"""Homepage contract for the privacy-conscious founder story."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_homepage_includes_parent_origin_story_without_child_identity() -> None:
    homepage = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert 'id="our-story"' in homepage
    assert "daughter is starting Year 3 in September 2026" in homepage
    assert "10–15 minutes" in homepage
    assert "helped shape the design and choose the name" in homepage
    assert "I’ll keep improving Homework Magic as my daughter uses it" in homepage
    assert 'href="/messages">I’d love to hear your feedback' in homepage


def test_founder_story_has_responsive_layout() -> None:
    theme = (ROOT / "static" / "css" / "theme.css").read_text(encoding="utf-8")

    assert ".hm-founder-story" in theme
    assert ".hm-founder-story { grid-template-columns: 1fr; }" in theme
