from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"


class _ScriptSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "script":
            return
        values = dict(attrs)
        source = values.get("src")
        if source:
            self.sources.append(source)


@pytest.mark.parametrize(
    "relative_path",
    [
        "app.html",
        "homework.html",
        "check-my-homework.html",
        "elevenplus-practice.html",
        "elevenplus-year-round-plan.html",
        "login.html",
        "register.html",
        "privacy.html",
        "safety.html",
    ],
)
def test_learner_and_account_pages_do_not_load_remote_scripts(relative_path: str) -> None:
    parser = _ScriptSourceParser()
    parser.feed((STATIC / relative_path).read_text(encoding="utf-8"))

    remote = [
        source
        for source in parser.sources
        if urlparse(source).scheme.casefold() in {"http", "https"}
    ]
    assert remote == [], f"Remote scripts are not allowed on {relative_path}: {remote}"
