"""Public and paid-access API tests for 11+ mock exams."""
from __future__ import annotations

from datetime import datetime, timezone

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


def test_mock_question_explanation_is_structured_and_reused_from_cache(client) -> None:
    """A second click should use the saved detailed explanation, not another LLM call."""
    exam_id = "common-diagnostic-1"
    question_id = "n07"

    first = client.post(
        f"/api/elevenplus/mock-exams/{exam_id}/questions/{question_id}/explanation"
    )

    assert first.status_code == 200, first.text
    first_payload = first.json()
    assert first_payload["success"] is True
    assert first_payload["from_saved"] is False
    assert "## How to solve it" in first_payload["explanation"]
    assert "## Why it works" in first_payload["explanation"]
    assert "## Helpful tip" in first_payload["explanation"]

    second = client.post(
        f"/api/elevenplus/mock-exams/{exam_id}/questions/{question_id}/explanation"
    )

    assert second.status_code == 200, second.text
    assert second.json()["from_saved"] is True
    assert second.json()["explanation"] == first_payload["explanation"]


def test_mock_question_explanation_falls_back_when_detail_llm_fails(client, monkeypatch) -> None:
    """An optional tutor outage must not leave a completed mock without help."""
    from src.webapp import review_service
    from src.elevenplus_mock_exams import _QUESTION_BY_ID
    from src.progress_db import list_mock_exam_explanations

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("temporary provider outage")

    monkeypatch.setattr(review_service, "_complete_review", unavailable)
    exam_id = "common-diagnostic-1"
    question_id = "n02"
    expected_working = _QUESTION_BY_ID[question_id]["explanation"]

    first = client.post(
        f"/api/elevenplus/mock-exams/{exam_id}/questions/{question_id}/explanation"
    )

    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["success"] is True
    assert payload["from_saved"] is False
    assert expected_working in payload["explanation"]
    assert "## How to solve it" in payload["explanation"]
    assert "## Why it works" in payload["explanation"]
    assert "## Helpful tip" in payload["explanation"]

    # It is saved even when the optional LLM was unavailable, so the next
    # click opens straight away and does not attempt another provider call.
    second = client.post(
        f"/api/elevenplus/mock-exams/{exam_id}/questions/{question_id}/explanation"
    )
    assert second.status_code == 200, second.text
    assert second.json()["from_saved"] is True
    assert second.json()["explanation"] == payload["explanation"]
    saved = next(
        row for row in list_mock_exam_explanations()
        if row["question_id"] == question_id
    )
    assert saved["model_used"] == "trusted_mock_fallback"


def test_mock_question_explanation_sends_the_actual_question_prompt_to_the_llm(
    client,
    app_module,
) -> None:
    """Mock question records use ``prompt``; never send an empty question to the tutor."""
    from src.elevenplus_mock_exams import _QUESTION_BY_ID

    class RecordingLLM:
        def __init__(self) -> None:
            self.requests = []

        def complete(self, messages, **_kwargs):
            self.requests.append(messages)
            return (
                "## How to solve it\nUse the information in the question.\n\n"
                "## Why it works\nIt checks every step.\n\n"
                "## Helpful tip\nRemember to check your working."
            )

    recorder = RecordingLLM()
    app_module.llm = recorder
    question_id = "m01"
    response = client.post(
        f"/api/elevenplus/mock-exams/common-diagnostic-1/questions/{question_id}/explanation"
    )

    assert response.status_code == 200, response.text
    assert recorder.requests
    prompt = recorder.requests[0][-1]["content"]
    assert _QUESTION_BY_ID[question_id]["prompt"] in prompt


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


def test_admin_mock_exam_statistics_are_aggregated_and_sortable(admin_client) -> None:
    assert set_user_test_flag('admin@example.com', True)
    started = admin_client.post('/api/elevenplus/mock-exams/common-full-1/start')
    assert started.status_code == 200
    payload = started.json()
    answers = {question['id']: 'A' for question in payload['questions']}
    submitted = admin_client.post(
        '/api/elevenplus/mock-exams/common-full-1/submit',
        json={'attempt_token': payload['attempt']['token'], 'answers': answers},
    )
    assert submitted.status_code == 200, submitted.text

    response = admin_client.get('/api/admin/mock-exam-statistics')
    assert response.status_code == 200, response.text
    data = response.json()
    row = next(item for item in data['statistics'] if item['exam_id'] == 'common-full-1')
    assert row['mock_name'] == 'Common Four-Subject Mock A'
    assert row['school_or_area'] == 'General / National'
    assert row['minutes'] == 45
    assert row['number_of_questions'] == 32
    assert row['student'] == ['admin@example.com + Learner']
    assert row['attempts'] == 1
    assert 0 <= row['overall_accuracy'] <= 100
    assert row['subject_breakdown']


def test_free_common_diagnostic_is_in_admin_mock_stats(monkeypatch, client, admin_client):
    from src import progress_db

    # This verifies the aggregate persistence path used by the free diagnostic,
    # including anonymous beta-style sessions that do not collect personal data.
    assert progress_db.save_mock_exam_attempt(
        "diagnostic-regression-attempt",
        "common-diagnostic-1",
        "anon_regression_student",
        8,
        10,
        [{"subject": "Maths", "correct": 4, "total": 5, "percent": 80}],
        datetime.fromtimestamp(1000, tz=timezone.utc),
        datetime.fromtimestamp(1100, tz=timezone.utc),
        allow_anonymous=True,
    ) is True
    stats = progress_db.get_admin_mock_exam_statistics(limit=2000)
    row = next(item for item in stats if item["exam_id"] == "common-diagnostic-1")
    assert row["attempts"] >= 1
