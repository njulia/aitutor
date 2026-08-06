"""Public and paid-access API tests for 11+ mock exams."""
from __future__ import annotations

import pytest


pytestmark = pytest.mark.api


def _contains_private_key(value) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"answer", "correct_answer", "explanation"}:
                return True
            if _contains_private_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_private_key(item) for item in value)
    return False


def test_anonymous_catalogue_offers_free_diagnostic_and_locks_paid_mocks(client) -> None:
    response = client.get("/api/elevenplus/mock-exams")

    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    data = response.json()
    assert any(item["is_free"] and item["available"] for item in data["exams"])
    assert any(not item["is_free"] and not item["available"] for item in data["exams"])
    assert not _contains_private_key(data)


def test_free_mock_can_be_started_and_scored_without_exposing_key(client) -> None:
    started = client.post("/api/elevenplus/mock-exams/common-diagnostic-1/start")

    assert started.status_code == 200
    payload = started.json()
    assert payload["attempt"]["token"]
    assert len(payload["questions"]) == 12
    assert not _contains_private_key(payload)

    answers = {question["id"]: "A" for question in payload["questions"]}
    submitted = client.post(
        "/api/elevenplus/mock-exams/common-diagnostic-1/submit",
        json={"attempt_token": payload["attempt"]["token"], "answers": answers},
    )

    assert submitted.status_code == 200
    result = submitted.json()
    assert result["score"]["total"] == 12
    assert result["score"]["answered"] == 12
    assert len(result["subject_breakdown"]) == 4
    assert all(item["correct_answer"] for item in result["questions"])


def test_tampered_attempt_token_is_rejected(client) -> None:
    started = client.post("/api/elevenplus/mock-exams/common-diagnostic-1/start")
    token = started.json()["attempt"]["token"]
    replacement = "A" if token[-1] != "A" else "B"

    submitted = client.post(
        "/api/elevenplus/mock-exams/common-diagnostic-1/submit",
        json={"attempt_token": token[:-1] + replacement, "answers": {}},
    )

    assert submitted.status_code == 400
    assert "start again" in submitted.json()["detail"].casefold()


def test_paid_mock_requires_parent_and_mock_plan(client) -> None:
    response = client.post("/api/elevenplus/mock-exams/common-full-1/start")

    assert response.status_code == 401
    assert response.json()["required_plan"] == "elevenplus_monthly"
    assert response.json()["required_plan_name"] == "11+ Premium"
