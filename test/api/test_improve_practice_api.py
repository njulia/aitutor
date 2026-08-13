from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def _request(question_index=None):
    return {
        "homework": "1. What is 4 + 3?",
        "answers": "1. 6",
        "subject": "Maths",
        "profile": {"year_group": 3, "age": 7},
        "review_feedback": "Check addition facts.",
        "homework_doc_id": "maths-set-1",
        "question_index": question_index,
    }


def test_no_usable_model_response_returns_clear_502(authenticated_client, app_module, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        app_module,
        "improve_practice",
        lambda *_args, **_kwargs: {
            "success": False,
            "error": "The AI tutor did not return any usable practice questions.",
            "llm_no_response": True,
        },
    )

    response = authenticated_client.post("/api/improve-practice", json=_request())

    assert response.status_code == 502
    assert response.json()["llm_no_response"] is True
    assert "did not return any usable practice questions" in response.json()["error"]


def test_tutor_question_index_reaches_improvement_service(authenticated_client, app_module, monkeypatch) -> None:
    captured = {}

    def fake_improve(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "practice": "## Similar Practice Questions\n1. What is 5 + 3?",
        }

    monkeypatch.setattr(app_module, "user_has_subscription", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(app_module, "improve_practice", fake_improve)

    response = authenticated_client.post("/api/improve-practice", json=_request(question_index=7))

    assert response.status_code == 200, response.text
    assert captured["question_index"] == 7

