from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_quick_review_flag_reaches_review_service_without_detail_subscription(
    authenticated_client, app_module, monkeypatch
) -> None:
    captured = {}

    def fake_review(_homework, _answers, _subject, _profile, **kwargs):
        captured.update(kwargs)
        return {"success": True, "review": "Quick feedback", "model_tier": "flash"}

    monkeypatch.setattr(app_module, "review_homework", fake_review)
    monkeypatch.setattr(
        app_module,
        "user_has_subscription",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Quick Review must not enter the detail-subscription path")
        ),
    )

    response = authenticated_client.post(
        "/api/review",
        json={
            "homework": "1. What is 2 + 3?\nA) 4\nB) 5",
            "answers": "1. B",
            "subject": "Maths",
            "profile": {"year_group": 3, "age": 7},
            "quick_review": True,
            "from_rag": True,
            "homework_doc_id": "maths-quick-review",
        },
    )

    assert response.status_code == 200, response.text
    assert captured["quick_review"] is True
    assert captured["is_tutor_mode"] is False


def test_browser_quick_review_request_sets_explicit_flag() -> None:
    from pathlib import Path

    source = Path("static/js/app.js").read_text(encoding="utf-8")
    function_body = source.split("async function reviewGeneratedHomework()", 1)[1].split(
        "function inferUploadedHomeworkSubject", 1
    )[0]
    assert "quick_review: true" in function_body



def test_anonymous_quick_review_requires_free_account(client) -> None:
    response = client.post(
        "/api/review",
        json={
            "homework": "1. What is 2 + 3?\nA) 4\nB) 5",
            "answers": "1. B",
            "subject": "Maths",
            "profile": {"year_group": 3, "age": 7},
            "quick_review": True,
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "registration_required"
