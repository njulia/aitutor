from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_year1_maths_generation_preserves_rag_metadata(client, app_module, monkeypatch) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        assert profile["year_group"] == 1
        assert subjects == ["Maths"]
        assert is_eleven_plus is False
        return [{
            "subject": "Maths",
            "content": "1. What is 2 + 3?",
            "doc_id": "math_y1_test_001",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)

    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 1,
            "subjects": ["Maths"],
            "mode": "homework",
            "profile": {},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    item = body["homework"][0]
    assert item["from_rag"] is True
    assert item["doc_id"] == "math_y1_test_001"
    assert item["is_eleven_plus"] is False


def test_tutor_mode_keeps_question_index_and_doc_id(client, app_module, monkeypatch) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        return [{
            "subject": "Maths",
            "content": "1. What is 1 + 1?\n2. What is 2 + 2?",
            "doc_id": "math_y1_two_questions",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)

    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 1,
            "subjects": ["Maths"],
            "mode": "tutor",
            "profile": {},
        },
    )
    assert response.status_code == 200, response.text
    homework = response.json()["homework"]
    assert [item["question_index"] for item in homework] == [0, 1]
    assert {item["doc_id"] for item in homework} == {"math_y1_two_questions"}
    assert all(item["from_rag"] is True for item in homework)


def test_review_route_passes_question_index_to_review_service(client, app_module, monkeypatch) -> None:
    captured = {}

    def fake_review(homework, answers, subject, profile, **kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "review": "Correct!",
            "score": 1,
            "max_score": 1,
            "attempted": 1,
            "correct_count": 1,
        }

    monkeypatch.setattr(app_module, "review_homework", fake_review)

    response = client.post(
        "/api/review",
        json={
            "homework": "What is 2 + 2?",
            "answers": "4",
            "subject": "Maths",
            "from_rag": True,
            "homework_doc_id": "math_y1_two_questions",
            "question_index": 1,
            "is_tutor_mode": True,
        },
    )
    assert response.status_code == 200, response.text
    assert captured["homework_doc_id"] == "math_y1_two_questions"
    assert captured["question_index"] == 1
    assert captured["is_tutor_mode"] is True
