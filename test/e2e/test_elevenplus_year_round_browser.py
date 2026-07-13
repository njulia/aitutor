from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e
BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


@pytest.fixture(autouse=True)
def require_e2e_enabled():
    if os.getenv("RUN_E2E", "0").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_E2E=1 and start the website to run browser tests")


def test_year_round_plan_renders_52_week_experience(page: Page) -> None:
    page.goto(f"{BASE_URL}/elevenplus-year-round-plan", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("52")
    expect(page.locator("body")).to_contain_text("Maths")
    expect(page.locator("body")).to_contain_text("English")
    # Foundations phase shows Maths and English for Week 1
    expect(page.locator(".phase-foundations")).to_be_visible()


def test_year_round_progress_uses_browser_storage_not_child_identity(page: Page) -> None:
    page.goto(f"{BASE_URL}/elevenplus-year-round-plan", wait_until="domcontentloaded")
    storage = page.evaluate("Object.fromEntries(Object.entries(localStorage))")
    serialised = str(storage).lower()
    assert "email" not in serialised
    assert "school" not in serialised
    assert "address" not in serialised


def test_year_round_mcq_hides_answers_and_shows_worked_feedback(page: Page) -> None:
    page.route(
        "**/api/generate",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='''{"success":true,"homework":[{"subject":"Maths","content":"QUESTIONS\\n1. What is 4 + 5?\\nA) 8\\nB) 9\\n2. Which is one half?\\nA) 0.2\\nB) 0.5","questions":[{"number":1,"question":"What is 4 + 5?","options":[{"label":"A","text":"8"},{"label":"B","text":"9"}]},{"number":2,"question":"Which is one half?","options":[{"label":"A","text":"0.2"},{"label":"B","text":"0.5"}]}],"doc_id":"week_01","from_rag":true,"plan_week":1,"content_type":"year_round"}],"profile":{"plan_week":1},"mode":"homework"}''',
        ),
    )
    page.route(
        "**/api/review",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='''{"success":true,"review":"## How to work out each answer\\n\\n### Question 1: Correct\\n\\n**How to get it:** Add 4 and 5 to make 9.","from_rag_answers":true,"correct_count":2,"attempted":2}''',
        ),
    )

    page.goto(f"{BASE_URL}/elevenplus-year-round-plan", wait_until="networkidle")
    page.get_by_role("button", name="Generate Week 1 practice").click()

    expect(page.locator(".practice-question")).to_have_count(2)
    expect(page.locator('input[type="radio"]')).to_have_count(4)
    expect(page.locator("#practice-results")).not_to_contain_text("Correct Answer")

    page.locator(".practice-question").nth(0).locator("input").nth(1).check()
    page.locator(".practice-question").nth(1).locator("input").nth(1).check()
    page.get_by_role("button", name="Check answers").click()

    expect(page.locator("#feedback-0")).to_contain_text("How to work out each answer")
    expect(page.locator("#feedback-0")).to_contain_text("Add 4 and 5 to make 9")
