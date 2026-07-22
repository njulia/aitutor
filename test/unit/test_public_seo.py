"""Search-engine contracts for the public Homework Magic website."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.webapp.runtime import CanonicalHostMiddleware


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
ORIGIN = "https://homeworkmagic.co.uk"

PUBLIC_PAGES = {
    "/": "index.html",
    "/ks1-homework": "ks1-homework.html",
    "/ks2-homework": "ks2-homework.html",
    "/elevenplus-practice": "elevenplus-practice.html",
    "/elevenplus-year-round-plan": "elevenplus-year-round-plan.html",
    "/elevenplus-topic-mastery": "elevenplus-topic-mastery.html",
    "/check-my-homework": "check-my-homework.html",
    "/pricing": "pricing.html",
    "/messages": "messages.html",
    "/safety": "safety.html",
    "/privacy": "privacy.html",
    "/terms": "terms.html",
    "/refund-policy": "refund-policy.html",
    "/elevenplus/articles": "elevenplus/articles.html",
    "/elevenplus/uk-grammar-guide": "elevenplus/uk_grammar_guide.html",
    "/elevenplus/11plus-vocabulary-list": "elevenplus/11plus_vocabulary_list.html",
    "/elevenplus/11plus-acceptance-rates-gcse": "elevenplus/11plus_acceptance_rates_gcse.html",
    "/elevenplus/11plus-maths-common-mistake": "elevenplus/11plus_maths_common_mistakes.html",
    "/elevenplus/11plus-school-guide": "elevenplus/11plus_school_guide.html",
    "/elevenplus/11plus-time-management": "elevenplus/11plus_time_management.html",
}


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonical = ""
        self.robots = ""
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag.casefold() == "link" and values.get("rel", "").casefold() == "canonical":
            self.canonical = values.get("href", "")
        if tag.casefold() == "meta" and values.get("name", "").casefold() == "robots":
            self.robots = values.get("content", "")
        if tag.casefold() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def test_every_sitemap_page_has_one_absolute_self_canonical() -> None:
    for route, relative_file in PUBLIC_PAGES.items():
        parser = _MetadataParser()
        parser.feed((STATIC / relative_file).read_text(encoding="utf-8"))

        expected = f"{ORIGIN}{route}" if route != "/" else f"{ORIGIN}/"
        assert parser.canonical == expected, relative_file
        assert parser.robots.casefold() == "index, follow", relative_file
        assert "".join(parser.title_parts).strip(), relative_file


def test_sitemap_contains_only_the_public_canonical_urls() -> None:
    tree = ET.parse(STATIC / "sitemap.xml")
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {node.text for node in tree.findall("s:url/s:loc", namespace)}
    expected = {
        f"{ORIGIN}{route}" if route != "/" else f"{ORIGIN}/"
        for route in PUBLIC_PAGES
    }

    assert locations == expected
    assert not any("www.homeworkmagic.co.uk" in location for location in locations)


def test_robots_endpoint_is_available_and_points_to_canonical_sitemap(client) -> None:
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in response.text
    assert f"Sitemap: {ORIGIN}/sitemap.xml" in response.text


def test_sitemap_endpoint_serves_the_current_static_sitemap(client) -> None:
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert f"<loc>{ORIGIN}/</loc>" in response.text


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("/elevenplus/11plus-acceptance-rates-gcse", "/elevenplus/11plus-acceptance-rates-gcse"),
        ("/elevenplus/11plus-maths-common-mistake", "/elevenplus/11plus-maths-common-mistake"),
        ("/elevenplus/11plus-time-management", "/elevenplus/11plus-time-management"),
        ("/contact-me", "/messages"),
    ],
)
def test_legacy_public_urls_redirect_permanently(client, legacy: str, canonical: str) -> None:
    response = client.get(legacy, follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == canonical


def test_public_pages_are_cacheable_but_static_html_implementation_urls_are_noindex(client) -> None:
    public_response = client.get("/")
    implementation_response = client.get("/static/index.html")

    assert public_response.status_code == 200
    assert public_response.headers["cache-control"].startswith("public, max-age=300")
    assert implementation_response.status_code == 200
    assert implementation_response.headers["x-robots-tag"] == "noindex, nofollow"


def test_www_host_redirects_to_the_configured_canonical_origin(monkeypatch) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("APP_BASE_URL", ORIGIN)
    monkeypatch.setenv("CANONICAL_REDIRECT_HOSTS", "www.homeworkmagic.co.uk")

    tiny_app = FastAPI()
    tiny_app.add_middleware(CanonicalHostMiddleware)

    @tiny_app.get("/check")
    async def check():
        return {"ok": True}

    with TestClient(tiny_app, base_url="https://www.homeworkmagic.co.uk") as test_client:
        response = test_client.get("/check?source=www", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == f"{ORIGIN}/check?source=www"
