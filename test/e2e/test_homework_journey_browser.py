from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def complete_homework_guide(
    page: Page,
    *,
    year: int = 2,
    subject: str = "Maths",
    minutes: int = 10,
    difficulty: str = "Gentle",
) -> None:
    page.get_by_role("button", name=f"Year {year}", exact=True).click()
    page.get_by_role("button", name=subject, exact=True).click()
    page.get_by_role("button", name=re.compile(rf"^{minutes} minutes")).click()
    page.get_by_role("button", name=re.compile(difficulty, re.I)).click()


def test_last_primary_year_and_subject_are_restored(
    page: Page,
    e2e_base_url: str,
    mock_common_app_endpoints,
) -> None:
    page.add_init_script(
        """
        if (!localStorage.getItem('homeworkMagic.learningChoices.v1')) {
          localStorage.setItem(
            'homeworkMagic.learningChoices.v1',
            JSON.stringify({
              homeworkYear: 5,
              homeworkSubject: 'English',
              homeworkMinutes: 15,
              homeworkDifficulty: 'just_right'
            })
          );
        }
        """
    )
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")

    expect(page.locator("#homework-quick-title")).to_have_text(
        "Ready for Year 5 English for 15 minutes?"
    )

    page.get_by_role("button", name="Change it").click()
    complete_homework_guide(
        page,
        year=4,
        subject="Science",
        minutes=20,
        difficulty="Challenge me",
    )
    expect(page.locator("#homework-guide-step-label")).to_have_text("Ready to start")
    page.reload(wait_until="domcontentloaded")

    expect(page.locator("#homework-quick-title")).to_have_text(
        "Ready for Year 4 Science for 20 minutes?"
    )


def test_legacy_descriptions_are_removed_and_parent_notes_are_not_saved(
    page: Page,
    e2e_base_url: str,
    mock_common_app_endpoints,
) -> None:
    page.add_init_script(
        """
        localStorage.setItem(
          'homeworkMagic.learningChoices.v1',
          JSON.stringify({
            homeworkPrompt: 'Mia enjoys fractions and needs help with times tables.',
            elevenPrompt: 'Leo is preparing for GL verbal reasoning.'
          })
        );
        """
    )
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")

    expect(page.locator("#homework-profile")).to_have_count(0)
    expect(page.locator("#homework-parent-notes")).to_have_value("")
    expect(page.locator("#eleven-profile")).to_have_count(0)
    expect(page.locator("#eleven-guide-question")).to_contain_text("What year")
    saved = page.evaluate(
        "() => JSON.parse(localStorage.getItem('homeworkMagic.learningChoices.v1') || '{}')"
    )
    assert "homeworkPrompt" not in saved
    assert "elevenPrompt" not in saved

    page.locator("#homework-parent-notes").fill("Fractions are tricky.")
    page.get_by_role("button", name=re.compile(r"11\+ practice", re.I)).click()
    page.get_by_role("button", name="Year 4").click()
    expect(page.locator("#eleven-guide-step-label")).to_have_text("Step 2 of 5")
    page.wait_for_timeout(500)
    page.reload(wait_until="domcontentloaded")

    expect(page.locator("#homework-parent-notes")).to_have_value("")
    expect(page.locator("#eleven-guide-step-label")).to_have_text("Step 1 of 5")


def test_primary_homework_generate_answer_and_review_journey(
    page: Page,
    e2e_base_url: str,
    fulfil_json,
    mock_common_app_endpoints,
) -> None:
    review_payloads: list[dict] = []

    page.route(
        "**/api/generate",
        lambda route: fulfil_json(
            route,
            {
                "success": True,
                "homework": [{
                    "subject": "Maths",
                    "content": "1. What is 3 + 4?\nA) 6\nB) 7\n2. Write the number after 9.",
                    "questions": [
                        {
                            "number": 1,
                            "question": "What is 3 + 4?",
                            "response_type": "single_choice",
                            "options": [
                                {"label": "A", "text": "6"},
                                {"label": "B", "text": "7"},
                            ],
                        },
                        {
                            "number": 2,
                            "question": "Write the number after 9.",
                            "response_type": "text",
                            "options": [],
                        },
                    ],
                    "doc_id": "maths_y2_e2e",
                    "from_rag": True,
                    "is_eleven_plus": False,
                }],
                "profile": {"year_group": 2, "age": 6},
                "mode": "homework",
            },
        ),
    )

    def handle_review(route) -> None:
        review_payloads.append(route.request.post_data_json or {})
        fulfil_json(
            route,
            {
                "success": True,
                "review": "## Great work\n\nBoth answers are correct. You added carefully and counted on by one.",
                "correct_count": 2,
                "attempted": 2,
                "score": 2,
                "max_score": 2,
            },
        )

    page.route("**/api/review", handle_review)
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")
    expect(page.locator("#homework-guide-question")).to_contain_text("What year")
    complete_homework_guide(page, year=2, subject="Maths", minutes=10, difficulty="Gentle")
    page.get_by_role("button", name="Make my homework", exact=False).click()

    expect(page.locator(".question-response-item")).to_have_count(2)
    page.locator(".multiple-choice-option").nth(1).click()
    page.locator(".question-response-input").fill("10")
    page.get_by_role("button", name="Quick Review").click()

    expect(page.locator("#review-result")).to_contain_text("Great work")
    expect(page.locator("#review-result")).to_contain_text("Both answers are correct")
    assert len(review_payloads) == 1
    payload = review_payloads[0]
    assert payload["answers"] == "1. 7\n2. 10"
    assert payload["profile"] == {"year_group": 2, "age": 6}
    assert payload["from_rag"] is True
    assert payload["homework_doc_id"] == "maths_y2_e2e"
    assert payload["quick_review"] is True
    serialised = str(payload).lower()
    assert "parent-e2e@example.com" not in serialised
    assert "student_id" not in payload["profile"]


def test_review_requires_every_visible_answer(
    page: Page,
    e2e_base_url: str,
    fulfil_json,
    mock_common_app_endpoints,
) -> None:
    review_called = False

    page.route(
        "**/api/generate",
        lambda route: fulfil_json(
            route,
            {
                "success": True,
                "homework": [{
                    "subject": "Maths",
                    "content": "1. What is 1 + 1?\nA) 2\nB) 3\n2. What comes after 4?",
                    "questions": [
                        {"number": 1, "question": "What is 1 + 1?", "response_type": "single_choice", "options": [
                            {"label": "A", "text": "2"}, {"label": "B", "text": "3"}
                        ]},
                        {"number": 2, "question": "What comes after 4?", "response_type": "text", "options": []},
                    ],
                    "doc_id": "incomplete_answers",
                    "from_rag": True,
                }],
                "profile": {"year_group": 1, "age": 5},
                "mode": "homework",
            },
        ),
    )

    def handle_review(route) -> None:
        nonlocal review_called
        review_called = True
        fulfil_json(route, {"success": True, "review": "Unexpected"})

    page.route("**/api/review", handle_review)
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")
    expect(page.locator("#homework-guide-question")).to_contain_text("What year")
    complete_homework_guide(page, year=1, subject="Maths", minutes=10, difficulty="Gentle")
    page.get_by_role("button", name="Make my homework", exact=False).click()
    page.locator(".multiple-choice-option").first.click()
    page.get_by_role("button", name="Quick Review").click()
    page.wait_for_timeout(200)

    assert review_called is False
    expect(page.locator(".question-response-input")).to_be_focused()
