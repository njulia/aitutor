from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_year_round_plan_renders_52_week_experience(page: Page, e2e_base_url: str) -> None:
    page.goto(f"{e2e_base_url}/elevenplus-year-round-plan", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("52")
    expect(page.locator("body")).to_contain_text("Maths")
    expect(page.locator("body")).to_contain_text("English")
    expect(page.locator(".phase-foundations")).to_be_visible()


def test_year_round_progress_uses_browser_storage_not_child_identity(
    page: Page, e2e_base_url: str
) -> None:
    page.goto(f"{e2e_base_url}/elevenplus-year-round-plan", wait_until="domcontentloaded")
    storage = page.evaluate("Object.fromEntries(Object.entries(localStorage))")
    serialised = str(storage).lower()
    assert "email" not in serialised
    assert "school" not in serialised
    assert "address" not in serialised


def test_year_round_mcq_hides_answers_and_shows_worked_feedback(
    page: Page, e2e_base_url: str, fulfil_json
) -> None:
    page.route(
        "**/api/generate",
        lambda route: fulfil_json(
            route,
            {
                "success": True,
                "homework": [{
                    "subject": "Maths",
                    "content": "QUESTIONS\n1. What is 4 + 5?\nA) 8\nB) 9\n2. Which is one half?\nA) 0.2\nB) 0.5",
                    "questions": [
                        {"number": 1, "question": "What is 4 + 5?", "options": [
                            {"label": "A", "text": "8"}, {"label": "B", "text": "9"}
                        ]},
                        {"number": 2, "question": "Which is one half?", "options": [
                            {"label": "A", "text": "0.2"}, {"label": "B", "text": "0.5"}
                        ]},
                    ],
                    "doc_id": "week_01",
                    "from_rag": True,
                    "plan_week": 1,
                    "content_type": "year_round",
                }],
                "profile": {"plan_week": 1},
                "mode": "homework",
            },
        ),
    )
    page.route(
        "**/api/review",
        lambda route: fulfil_json(
            route,
            {
                "success": True,
                "review": "## How to work out each answer\n\n### Question 1: Correct\n\n**How to get it:** Add 4 and 5 to make 9.",
                "from_rag_answers": True,
                "correct_count": 2,
                "attempted": 2,
            },
        ),
    )

    page.goto(f"{e2e_base_url}/elevenplus-year-round-plan", wait_until="domcontentloaded")
    page.get_by_role("button", name="Generate Week 1 practice").click()

    expect(page.locator(".practice-question")).to_have_count(2)
    expect(page.locator('input[type="radio"]')).to_have_count(4)
    expect(page.locator("#practice-results")).not_to_contain_text("Correct Answer")

    page.locator(".practice-question").nth(0).locator("label").nth(1).click()
    page.locator(".practice-question").nth(1).locator("label").nth(1).click()
    page.get_by_role("button", name="Check answers").click()

    expect(page.locator("#feedback-0")).to_contain_text("How to work out each answer")
    expect(page.locator("#feedback-0")).to_contain_text("Add 4 and 5 to make 9")
