from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


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
            JSON.stringify({homeworkYear: 5, homeworkSubject: 'English'})
          );
        }
        """
    )
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")

    expect(page.locator("#homework-subjects .subject-item").first).to_be_visible()
    expect(page.locator("#homework-year")).to_have_value("5")
    expect(page.locator('#homework-subjects .subject-item[data-subject="English"]')).to_have_class(
        re.compile(r"\bselected\b")
    )

    page.locator("#homework-year").select_option("4")
    page.locator('#homework-subjects .subject-item[data-subject="Science"]').click()
    page.reload(wait_until="domcontentloaded")

    expect(page.locator("#homework-year")).to_have_value("4")
    expect(page.locator('#homework-subjects .subject-item[data-subject="Science"]')).to_have_class(
        re.compile(r"\bselected\b")
    )


def test_last_tell_me_about_entries_are_restored(
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

    expect(page.locator("#homework-profile")).to_have_value(
        "Mia enjoys fractions and needs help with times tables."
    )
    expect(page.locator("#eleven-profile")).to_have_value(
        "Leo is preparing for GL verbal reasoning."
    )

    page.locator("#homework-profile").fill("Mia would like more Year 4 fractions practice.")
    page.get_by_role("button", name=re.compile(r"11\+ practice", re.I)).click()
    page.locator("#eleven-profile").fill("Leo is now focusing on GL English comprehension.")
    page.wait_for_timeout(500)
    page.reload(wait_until="domcontentloaded")

    expect(page.locator("#homework-profile")).to_have_value(
        "Mia would like more Year 4 fractions practice."
    )
    expect(page.locator("#eleven-profile")).to_have_value(
        "Leo is now focusing on GL English comprehension."
    )


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
    expect(page.locator("#homework-subjects .subject-item").first).to_be_visible()
    page.locator("#homework-year").select_option("2")
    page.get_by_role("button", name="Generate Homework", exact=True).click()

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
    expect(page.locator("#homework-subjects .subject-item").first).to_be_visible()
    page.get_by_role("button", name="Generate Homework", exact=True).click()
    page.locator(".multiple-choice-option").first.click()
    page.get_by_role("button", name="Quick Review").click()
    page.wait_for_timeout(200)

    assert review_called is False
    expect(page.locator(".question-response-input")).to_be_focused()
