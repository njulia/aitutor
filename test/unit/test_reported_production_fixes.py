from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.admin import subscription_duration_days
from src.webapp.review_service import _table


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_multiline_multiple_choice_question_stays_inside_summary_table() -> None:
    summary = _table(
        [
            {
                "is_correct": False,
                "question": (
                    "1. It is 4:00. What time is it 30 minutes later?\n\n"
                    "A. 4:45\n\nB. 4:30\n\nC. 5:00\n\nD. 4:15"
                ),
                "student_answer": "4:15",
                "correct_answer": "4:30",
            }
        ]
    )

    assert "## Homework Review Summary" in summary
    assert "\n\nA. 4:45" not in summary
    assert "| ❌ | 1. It is 4:00." in summary
    assert summary.count("| ❌ |") == 1
    assert "D. 4:15 | 4:15 | 4:30 |" in summary


@pytest.mark.parametrize(
    ("start", "expected_days"),
    [
        (datetime(2026, 7, 22, tzinfo=UTC), 31),
        (datetime(2026, 1, 31, tzinfo=UTC), 28),
        (datetime(2026, 12, 22, tzinfo=UTC), 31),
    ],
)
def test_one_month_admin_access_uses_a_calendar_month(
    start: datetime, expected_days: int
) -> None:
    assert subscription_duration_days("1_month", start) == expected_days


def test_review_actions_follow_the_review_result() -> None:
    page = (ROOT / "static" / "app.html").read_text(encoding="utf-8")

    result_position = page.index('id="review-result"')
    assert result_position < page.index('id="homework-buttons"')
    assert result_position < page.index('id="tutor-mode-buttons"')


def test_web_app_explanation_wrapper_uses_the_maintained_prompt_contract(
    app_module,
) -> None:
    result = app_module.explain_deep(
        "1. What is 2 + 2?",
        "4",
        "Maths",
        {"year_group": 2, "age": 6},
        "The answer was correct.",
    )

    assert result["success"] is True
    assert "correct_answers_section" not in str(result)


def test_explain_in_detail_endpoint_no_longer_raises_missing_prompt_field(
    client, app_module, monkeypatch
) -> None:
    monkeypatch.setattr(
        app_module,
        "user_has_subscription",
        lambda *args, **kwargs: True,
    )

    response = client.post(
        "/api/explain-deep",
        json={
            "homework": "1. What is 2 + 2?",
            "answers": "4",
            "subject": "Maths",
            "profile": {"year_group": 2, "age": 6},
            "review_feedback": "The answer was correct.",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert "correct_answers_section" not in response.text


def test_memory_page_is_mounted(client) -> None:
    response = client.get("/memory")

    assert response.status_code == 200
    assert "Learning memory" in response.text
