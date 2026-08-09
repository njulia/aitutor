"""Search-engine contracts for the public Homework Magic website."""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
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
    "/year-3-maths-practice": "year-3-maths-practice.html",
    "/year-3-english-reading-practice": "year-3-english-reading-practice.html",
    "/calm-eleven-plus-practice": "calm-eleven-plus-practice.html",
    "/elevenplus-practice": "elevenplus-practice.html",
    "/elevenplus-mock-exams": "elevenplus-mock-exams.html",
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
    "/elevenplus/11plus-exam-formats": "elevenplus/11plus-exam-formats.html",
    "/elevenplus/11plus-preparation-timeline": "elevenplus/11plus-preparation-timeline.html",
    "/elevenplus/comprehension-question-types": "elevenplus/comprehension-question-types.html",
    "/elevenplus/english-comprehension-strategies": "elevenplus/english-comprehension-strategies.html",
    "/elevenplus/essay-writing-guide": "elevenplus/essay-writing-guide.html",
    "/elevenplus/exam-day-preparation": "elevenplus/exam-day-preparation.html",
    "/elevenplus/fractions-decimals-percentages": "elevenplus/fractions-decimals-percentages.html",
    "/elevenplus/geometry-algebra-fundamentals": "elevenplus/geometry-algebra-fundamentals.html",
    "/elevenplus/managing-test-anxiety": "elevenplus/managing-test-anxiety.html",
    "/elevenplus/maths-topics-checklist": "elevenplus/maths-topics-checklist.html",
    "/elevenplus/mock-exam-strategy": "elevenplus/mock-exam-strategy.html",
    "/elevenplus/non-verbal-reasoning-guide": "elevenplus/non-verbal-reasoning-guide.html",
    "/elevenplus/problem-solving-techniques": "elevenplus/problem-solving-techniques.html",
    "/elevenplus/revision-techniques": "elevenplus/revision-techniques.html",
    "/elevenplus/selective-schools-admission": "elevenplus/selective-schools-admission.html",
    "/elevenplus/spatial-awareness-practice": "elevenplus/spatial-awareness-practice.html",
    "/elevenplus/spelling-punctuation-grammar": "elevenplus/spelling-punctuation-grammar.html",
    "/elevenplus/stress-management-techniques": "elevenplus/stress-management-techniques.html",
    "/elevenplus/supporting-child-preparation": "elevenplus/supporting-child-preparation.html",
    "/elevenplus/tutoring-vs-self-study": "elevenplus/tutoring-vs-self-study.html",
    "/elevenplus/verbal-reasoning-tips": "elevenplus/verbal-reasoning-tips.html",
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


def test_mock_exam_page_has_matching_faq_schema_and_current_plan_price() -> None:
    source = (STATIC / "elevenplus-mock-exams.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        source,
        re.DOTALL,
    )
    assert match
    graph = json.loads(match.group(1))["@graph"]
    types = {item["@type"] for item in graph}
    assert {"WebPage", "SoftwareApplication", "BreadcrumbList", "FAQPage"} <= types
    faq = next(item for item in graph if item["@type"] == "FAQPage")
    assert len(faq["mainEntity"]) == 5
    assert all(item["name"] in source for item in faq["mainEntity"])
    application = next(item for item in graph if item["@type"] == "SoftwareApplication")
    assert {offer["price"] for offer in application["offers"]} == {"0", "9.99"}
    assert "14.99" not in source
    assert "free diagnostic" in source.casefold()
    assert "Only the Common 11+ Diagnostic is free" in source
    assert "every other mock" in source.casefold()
    assert "29 online 11 Plus mock exams" in source
    assert "278 original questions" in source
    assert "eight common papers" in source
    assert all(
        area in source
        for area in (
            "Wilson's",
            "Tiffin Girls",
            "St Olave's",
            "Henrietta Barnett",
            "Altrincham Girls",
            "Reading",
            "CCHS",
            "Kent",
            "Buckinghamshire",
            "Sutton",
            "West Midlands",
            "CSSE Essex",
            "Lancaster",
            "Bexley",
            "Wirral",
            "Gloucestershire",
            "Slough",
            "Medway",
        )
    )


def test_mock_exam_frontend_and_pricing_name_the_premium_boundary() -> None:
    page = (STATIC / "elevenplus-mock-exams.html").read_text(encoding="utf-8")
    javascript = (STATIC / "js" / "mock-exams.js").read_text(encoding="utf-8")
    pricing = (STATIC / "pricing.html").read_text(encoding="utf-8")

    assert "20260806-premium-access" in page
    assert "Free:</strong> Common 11+ Diagnostic" in page
    assert "11+ Premium:</strong> every other mock exam" in page
    assert "Requires an active 11+ Premium subscription." in javascript
    assert "Get 11+ Premium" in javascript
    assert "other mocks require 11+ Premium" in pricing


def test_mock_exam_sitemap_entry_has_a_last_modified_date() -> None:
    tree = ET.parse(STATIC / "sitemap.xml")
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for entry in tree.findall("s:url", namespace):
        if entry.findtext("s:loc", namespaces=namespace) == f"{ORIGIN}/elevenplus-mock-exams":
            assert entry.findtext("s:lastmod", namespaces=namespace) == "2026-08-09"
            break
    else:
        pytest.fail("Mock-exam sitemap entry not found")


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
        ("/elevenplus/11plus_acceptance_rates_gcse", "/elevenplus/11plus-acceptance-rates-gcse"),
        ("/elevenplus/11plus_maths_common_mistakes", "/elevenplus/11plus-maths-common-mistake"),
        ("/elevenplus/11plus_time_management", "/elevenplus/11plus-time-management"),
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
