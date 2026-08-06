"""Role-safe multi-learner family session contracts."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.webapp.account_store import create_subscription
from src.webapp.reward_store import get_reward_store, review_fingerprint


pytestmark = pytest.mark.api


def _award_points(account_id: str, student_id: str) -> None:
    store = get_reward_store()
    now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    for offset in range(5):
        for subject in ("Maths", "English", "Science"):
            store.award_checked_activity(
                account_id=account_id,
                student_id=student_id,
                fingerprint=review_fingerprint(
                    homework=f"Family session activity {offset} {subject}",
                    answers=f"Family session answer {offset} {subject}",
                    subject=subject,
                ),
                subject=subject,
                gift_points_eligible=True,
                awarded_at=now - timedelta(days=offset),
            )


def test_parent_can_add_edit_and_select_multiple_learners(
    authenticated_client,
) -> None:
    context = authenticated_client.get("/api/session-context")
    assert context.status_code == 200
    assert context.json()["role"] == "parent"
    assert len(context.json()["students"]) == 1
    assert context.json()["student_limit"] >= 2

    first = context.json()["students"][0]
    edited = authenticated_client.put(
        f"/api/students/{first['id']}",
        json={"name": "Ava", "year_group": 4, "age": 8},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["student"]["name"] == "Ava"

    added = authenticated_client.post(
        "/api/students",
        json={"name": "Leo", "year_group": 2, "age": 6},
    )
    assert added.status_code == 200, added.text
    overview = authenticated_client.get("/api/parent/overview")
    assert overview.status_code == 200, overview.text
    assert {kid["name"] for kid in overview.json()["kids"]} == {"Ava", "Leo"}
    assert all("progress" in kid and "wallet" in kid for kid in overview.json()["kids"])


def test_kid_session_is_limited_to_own_progress_rewards_and_mock_access(
    authenticated_client,
) -> None:
    account_data = authenticated_client.get("/api/account").json()
    account = account_data["account"]
    first = account_data["students"][0]
    second_response = authenticated_client.post(
        "/api/students",
        json={"name": "Sibling", "year_group": 5, "age": 9},
    )
    assert second_response.status_code == 200, second_response.text
    sibling = second_response.json()["student"]
    create_subscription(
        account_id=account["id"],
        plan="elevenplus_monthly",
        status="active",
        duration_days=30,
    )
    _award_points(account["id"], first["id"])

    assert len(str(account["family_code"]).replace("FAM-", "")) == 6
    assert len(str(first["kid_code"]).replace("KID-", "")) == 6
    login_code = (
        f"{str(account['family_code']).replace('FAM-', '')}-"
        f"{str(first['kid_code']).replace('KID-', '')}"
    )
    login = authenticated_client.post(
        "/api/kid-login", json={"login_code": login_code}
    )
    assert login.status_code == 200, login.text

    context = authenticated_client.get("/api/session-context")
    assert context.status_code == 200
    assert context.json()["role"] == "kid"
    assert context.json()["student"]["id"] == first["id"]
    assert "kid_code" not in context.text and "family_code" not in context.text
    assert authenticated_client.get("/api/account").status_code == 401

    own_progress = authenticated_client.get(f"/api/progress/{first['id']}")
    assert own_progress.status_code == 200, own_progress.text
    sibling_progress = authenticated_client.get(f"/api/progress/{sibling['id']}")
    assert sibling_progress.status_code == 403

    own_rewards = authenticated_client.get(f"/api/rewards?student_id={first['id']}")
    assert own_rewards.status_code == 200, own_rewards.text
    sibling_rewards = authenticated_client.get(
        f"/api/rewards?student_id={sibling['id']}"
    )
    assert sibling_rewards.status_code == 403

    requested = authenticated_client.post(
        "/api/rewards/redemptions",
        json={
            "student_id": first["id"],
            "reward_code": "homework_magic_stickers",
        },
    )
    assert requested.status_code == 200, requested.text
    certificate = authenticated_client.get(
        f"/rewards/certificate/brilliant_beginner?student_id={first['id']}"
    )
    assert certificate.status_code == 200, certificate.text

    mock = authenticated_client.post(
        "/api/elevenplus/mock-exams/common-full-1/start"
    )
    assert mock.status_code == 200, mock.text


def test_parent_login_replaces_a_kid_session(authenticated_client, unique_email) -> None:
    account_data = authenticated_client.get("/api/account").json()
    account = account_data["account"]
    learner = account_data["students"][0]
    login_code = f"{account['family_code']}-{learner['kid_code']}"
    kid_login = authenticated_client.post(
        "/api/kid-login", json={"login_code": login_code}
    )
    assert kid_login.status_code == 200
    assert authenticated_client.get("/api/session-context").json()["role"] == "kid"

    parent_login = authenticated_client.post(
        "/api/login",
        json={"email": unique_email, "password": "StrongPass123!"},
    )
    assert parent_login.status_code == 200, parent_login.text
    assert authenticated_client.get("/api/session-context").json()["role"] == "parent"
