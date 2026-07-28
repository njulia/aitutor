from __future__ import annotations

import pytest


pytestmark = pytest.mark.api


def test_uploaded_text_file_can_be_read_and_reviewed(
    client, app_module, monkeypatch
) -> None:
    captured = {}

    def fake_review(homework, answers, subject, profile, **kwargs):
        captured.update(
            homework=homework,
            answers=answers,
            subject=subject,
            profile=profile,
            **kwargs,
        )
        return {
            "success": True,
            "review": "## Score\n\n**2/2**\n\n## Keep Going\n\nWell done!",
            "model_tier": "flash",
        }

    monkeypatch.setattr(app_module, "review_homework", fake_review)
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *_args, **_kwargs: True)

    upload = client.post(
        "/api/upload-file",
        files={
            "file": (
                "worksheet.txt",
                b"Questions\\n1. What is 2 + 3?\\n2. What is 8 - 2?"
                b"\\nAnswers\\n1. 5\\n2. 6",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200, upload.text
    extracted = upload.json()["content"]
    assert "What is 2 + 3?" in extracted

    review = client.post(
        "/api/review",
        json={
            "homework": "1. What is 2 + 3?\n2. What is 8 - 2?",
            "answers": "1. 5\n2. 6",
            "subject": "Maths",
            "profile": {"year_group": 2, "age": 6},
            "uploaded_work": True,
        },
    )

    assert review.status_code == 200, review.text
    assert review.json()["success"] is True
    assert captured["uploaded_work"] is True
    assert captured["quick_review"] is False


def test_uploaded_review_remains_subscription_protected(
    client, app_module, monkeypatch
) -> None:
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *_args, **_kwargs: False)
    response = client.post(
        "/api/review",
        json={
            "homework": "1. What is 2 + 2?",
            "answers": "1. 4",
            "subject": "Maths",
            "uploaded_work": True,
        },
    )

    assert response.status_code == 401
    assert "Mark uploaded homework" in response.json()["error"]


def test_browser_marks_file_and_photo_reviews_as_uploaded_work() -> None:
    from pathlib import Path

    source = Path("static/js/app.js").read_text(encoding="utf-8")
    review_body = source.split("async function reviewHomework()", 1)[1].split(
        "function buildGeneratedReviewContext", 1
    )[0]

    assert "currentInputMethod === 'file' || currentInputMethod === 'photo'" in review_body
    assert "uploaded_work: Boolean(submittedWork)" in review_body
