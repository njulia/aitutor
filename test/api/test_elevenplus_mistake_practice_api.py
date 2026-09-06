"""API coverage for the combined 11+ Mistake Practice page."""
from __future__ import annotations

import pytest

from src import progress_db


pytestmark = pytest.mark.api


def test_11plus_mistake_page_combines_every_learning_source_by_topic(
    client,
    app_module,
    monkeypatch,
) -> None:
    student_id = "combined-11plus-mistakes"

    async def identity(_request):
        return student_id, "parent@example.com", None

    async def registered(*_args, **_kwargs):
        return None

    monkeypatch.setattr(app_module, "_resolve_request_identity", identity)
    monkeypatch.setattr(app_module, "_require_registered_identity", registered)
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *_args, **_kwargs: True)

    progress_db.save_mistake_questions(student_id, [
        {
            "question": "Practice fractions question",
            "subject": "Maths",
            "topic": "Fractions",
            "correct_answer": "A",
            "source_type": "11plus_practice",
        },
        {
            "question": "Topic Mastery fractions question",
            "subject": "Maths",
            "topic": "Fractions",
            "correct_answer": "B",
            "source_type": "topic_mastery",
        },
        {
            "question": "Year-Round comprehension question",
            "subject": "English",
            "topic": "Comprehension",
            "correct_answer": "C",
            "source_type": "year_round",
        },
        {
            "question": "Mock exam comprehension question",
            "subject": "English",
            "topic": "Comprehension",
            "correct_answer": "D",
            "source_type": "mock_exam",
        },
    ])

    summary = client.get("/api/elevenplus/mistake-practice?summary=true&limit=1")

    assert summary.status_code == 200, summary.text
    payload = summary.json()
    assert payload["topic_counts"] == [
        {"subject": "English", "topic": "Comprehension", "count": 2},
        {"subject": "Maths", "topic": "Fractions", "count": 2},
    ]

    filtered = client.get(
        "/api/elevenplus/mistake-practice?subject=Maths&topic=Fractions&limit=20"
    )

    assert filtered.status_code == 200, filtered.text
    questions = filtered.json()["questions"]
    assert {item["source_type"] for item in questions} == {
        "11plus_practice",
        "topic_mastery",
    }
    assert all("correct_answer" not in item for item in questions)
    assert all("correct_letter" not in item for item in questions)
