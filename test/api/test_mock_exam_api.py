"""Public and paid-access API tests for 11+ mock exams."""
from __future__ import annotations

import pytest

from src.webapp.account_store import create_subscription
from src.webapp import mock_exam_routes
from src.progress_db import set_user_test_flag


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


def test_free_mock_stays_public_when_entitlement_lookup_is_unavailable(
    client,
    monkeypatch,
) -> None:
    """The public diagnostic never depends on a subscription lookup."""

    async def unavailable(*_args, **_kwargs):
        raise RuntimeError("subscription store unavailable")

    monkeypatch.setattr(mock_exam_routes, "run_blocking", unavailable)

    catalogue = client.get("/api/elevenplus/mock-exams")
    assert catalogue.status_code == 200
    exams = catalogue.json()["exams"]
    diagnostic = next(item for item in exams if item["id"] == "common-diagnostic-1")
    assert diagnostic["is_free"] is True
    assert diagnostic["available"] is True
    assert all(
        item["available"] is False
        for item in exams
        if item["id"] != "common-diagnostic-1"
    )

    started = client.post(
        "/api/elevenplus/mock-exams/common-diagnostic-1/start"
    )
    assert started.status_code == 200


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


def test_five_day_access_does_not_unlock_paid_mock_exams(
    authenticated_client,
) -> None:
    account = authenticated_client.get("/api/account").json()["account"]
    create_subscription(
        account_id=account["id"],
        plan="trial_5day",
        status="active",
        duration_days=5,
    )

    catalogue = authenticated_client.get("/api/elevenplus/mock-exams")
    assert catalogue.status_code == 200
    exams = catalogue.json()["exams"]
    diagnostic = next(item for item in exams if item["id"] == "common-diagnostic-1")
    paid = [item for item in exams if item["id"] != "common-diagnostic-1"]
    assert diagnostic["is_free"] is True
    assert diagnostic["available"] is True
    assert all(item["is_free"] is False for item in paid)
    assert all(item["available"] is False for item in paid)
    assert all(item["required_plan"] == "elevenplus_monthly" for item in paid)

    free_start = authenticated_client.post(
        "/api/elevenplus/mock-exams/common-diagnostic-1/start"
    )
    paid_start = authenticated_client.post(
        "/api/elevenplus/mock-exams/common-full-1/start"
    )
    assert free_start.status_code == 200
    assert paid_start.status_code == 402
    assert paid_start.json()["required_plan_name"] == "11+ Premium"


def test_test_account_unlocks_all_paid_mock_exams(
    authenticated_client,
    unique_email,
) -> None:
    """Test users bypass the subscription check for all 11+ mock exams."""
    assert set_user_test_flag(unique_email, True)

    catalogue = authenticated_client.get("/api/elevenplus/mock-exams")
    paid = [item for item in catalogue.json()["exams"] if not item["is_free"]]
    assert paid
    assert all(item["available"] is True for item in paid)

    started = authenticated_client.post(
        "/api/elevenplus/mock-exams/common-full-1/start"
    )
    assert started.status_code == 200


def test_test_account_kid_session_unlocks_all_paid_mock_exams(
    authenticated_client,
    unique_email,
) -> None:
    """A test parent's kid login inherits the mock-exam test entitlement."""
    assert set_user_test_flag(unique_email, True)
    account_data = authenticated_client.get("/api/account").json()
    account = account_data["account"]
    learner = account_data["students"][0]
    login_code = f"{account['family_code']}-{learner['kid_code']}"

    logged_in = authenticated_client.post(
        "/api/kid-login",
        json={"login_code": login_code},
    )
    assert logged_in.status_code == 200, logged_in.text

    catalogue = authenticated_client.get("/api/elevenplus/mock-exams")
    paid = [item for item in catalogue.json()["exams"] if not item["is_free"]]
    assert paid
    assert all(item["available"] is True for item in paid)

    started = authenticated_client.post(
        "/api/elevenplus/mock-exams/common-full-1/start"
    )
    assert started.status_code == 200, started.text


def test_free_and_test_user_paid_starts_accept_long_session_owner_secret(
    authenticated_client,
    unique_email,
    monkeypatch,
) -> None:
    """Secret Manager newlines must not stop either shared start path."""
    assert set_user_test_flag(unique_email, True)
    monkeypatch.setenv("SESSION_OWNER_SECRET", ("A" * 64) + "\n")

    free_started = authenticated_client.post(
        "/api/elevenplus/mock-exams/common-diagnostic-1/start"
    )
    paid_started = authenticated_client.post(
        "/api/elevenplus/mock-exams/common-full-1/start"
    )

    assert free_started.status_code == 200, free_started.text
    assert paid_started.status_code == 200, paid_started.text
    assert free_started.json()["attempt"]["token"]
    assert paid_started.json()["attempt"]["token"]


def test_elevenplus_premium_unlocks_every_paid_mock(authenticated_client) -> None:
    account = authenticated_client.get("/api/account").json()["account"]
    create_subscription(
        account_id=account["id"],
        plan="elevenplus_monthly",
        status="active",
        duration_days=30,
    )

    catalogue = authenticated_client.get("/api/elevenplus/mock-exams")
    exams = catalogue.json()["exams"]
    paid = [item for item in exams if item["id"] != "common-diagnostic-1"]
    assert paid
    assert all(item["available"] is True for item in paid)
    assert all(item["required_plan"] == "elevenplus_monthly" for item in paid)

    for exam in paid:
        started = authenticated_client.post(
            f"/api/elevenplus/mock-exams/{exam['id']}/start"
        )
        assert started.status_code == 200, started.text
        payload = started.json()
        assert len(payload["questions"]) == exam["question_count"]
        assert not _contains_private_key(payload)
