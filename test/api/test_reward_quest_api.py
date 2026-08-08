from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.webapp.reward_store import get_reward_store, review_fingerprint

DELIVERY_ADDRESS = {
    "recipient_name": "Alex Parent",
    "address_line1": "10 High Street",
    "address_line2": "",
    "town_city": "London",
    "postcode": "SW1A 1AA",
    "country": "GB",
    "adult_recipient_confirmed": True,
}


def _award_sticker_points(account_id: str, student_id: str) -> None:
    store = get_reward_store()
    now = datetime.now(UTC).replace(
        hour=12,
        minute=0,
        second=0,
        microsecond=0,
    )
    for day_offset in range(5):
        awarded_at = now - timedelta(days=day_offset)
        for index, subject in enumerate(
            ("Maths", "English", "Science"),
            start=1,
        ):
            store.award_checked_activity(
                account_id=account_id,
                student_id=student_id,
                fingerprint=review_fingerprint(
                    homework=(
                        f"API worksheet {day_offset}-{index}"
                    ),
                    answers=f"API answer {day_offset}-{index}",
                    subject=subject,
                ),
                subject=subject,
                gift_points_eligible=True,
                awarded_at=awarded_at,
            )


def test_reward_dashboard_requires_a_parent_account(client) -> None:
    response = client.get("/api/rewards")
    assert response.status_code == 401
    assert "parent or guardian" in response.text.lower()


def test_reward_request_parent_approval_and_certificate(
    authenticated_client, unique_email
) -> None:
    account_response = authenticated_client.get("/api/account")
    assert account_response.status_code == 200
    account_body = account_response.json()
    account = account_body["account"]
    learner = account_body["students"][0]
    _award_sticker_points(account["id"], learner["id"])

    dashboard = authenticated_client.get(
        f"/api/rewards?student_id={learner['id']}"
    )
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()
    assert data["wallet"]["lifetime_xp"] >= 500
    gift_points_before = data["wallet"]["gift_points"]
    lifetime_xp_before = data["wallet"]["lifetime_xp"]
    assert any(item["unlocked"] for item in data["certificates"])

    request = authenticated_client.post(
        "/api/rewards/redemptions",
        json={
            "student_id": learner["id"],
            "reward_code": "homework_magic_stickers",
        },
    )
    assert request.status_code == 200, request.text
    redemption = request.json()["redemption"]
    assert redemption["status"] == "pending"

    wrong_password = authenticated_client.post(
        f"/api/rewards/redemptions/{redemption['id']}/decision",
        json={"decision": "approve", "parent_password": "NotThePassword"},
    )
    assert wrong_password.status_code == 403

    missing_address = authenticated_client.post(
        f"/api/rewards/redemptions/{redemption['id']}/decision",
        json={"decision": "approve", "parent_password": "StrongPass123!"},
    )
    assert missing_address.status_code == 400

    approved = authenticated_client.post(
        f"/api/rewards/redemptions/{redemption['id']}/decision",
        json={
            "decision": "approve",
            "parent_password": "StrongPass123!",
            "delivery_address": DELIVERY_ADDRESS,
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["redemption"]["status"] == "approved"
    assert approved.json()["wallet"]["lifetime_xp"] == lifetime_xp_before
    assert (
        approved.json()["wallet"]["gift_points"]
        == gift_points_before - 500
    )
    assert "Alex Parent" not in approved.text
    assert "SW1A 1AA" not in approved.text

    certificate = authenticated_client.get(
        f"/rewards/certificate/brilliant_beginner?student_id={learner['id']}"
    )
    assert certificate.status_code == 200
    assert learner["name"] in certificate.text
    assert certificate.headers["cache-control"] == "no-store, private"
    assert "noindex" in certificate.headers["x-robots-tag"]


def test_admin_can_dispatch_without_exposing_address_to_child(
    authenticated_client,
) -> None:
    account_body = authenticated_client.get("/api/account").json()
    account = account_body["account"]
    learner = account_body["students"][0]
    _award_sticker_points(account["id"], learner["id"])
    requested = authenticated_client.post(
        "/api/rewards/redemptions",
        json={
            "student_id": learner["id"],
            "reward_code": "homework_magic_stickers",
        },
    )
    assert requested.status_code == 200, requested.text
    order_id = requested.json()["redemption"]["id"]
    approved = authenticated_client.post(
        f"/api/rewards/redemptions/{order_id}/decision",
        json={
            "decision": "approve",
            "parent_password": "StrongPass123!",
            "delivery_address": DELIVERY_ADDRESS,
        },
    )
    assert approved.status_code == 200, approved.text

    child_dashboard = authenticated_client.get("/api/rewards")
    assert child_dashboard.status_code == 200
    assert "Alex Parent" not in child_dashboard.text
    assert "SW1A 1AA" not in child_dashboard.text

    authenticated_client.post("/api/logout")
    registered = authenticated_client.post(
        "/api/register",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    if registered.status_code == 400:
        registered = authenticated_client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "StrongPass123!"},
        )
    assert registered.status_code == 200, registered.text

    detail = authenticated_client.get(f"/api/admin/reward-orders/{order_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["delivery_address"]["postcode"] == "SW1A 1AA"

    dispatched = authenticated_client.post(
        f"/api/admin/reward-orders/{order_id}/decision",
        json={"decision": "dispatch"},
    )
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["redemption"]["status"] == "dispatched"


def test_family_cannot_read_another_learners_rewards(
    client, unique_email
) -> None:
    first = client.post(
        "/api/register",
        json={
            "email": unique_email,
            "password": "StrongPass123!",
            "guardian_confirmed": True,
        },
    )
    assert first.status_code == 200
    other_learner = client.get("/api/account").json()["students"][0]["id"]
    client.post("/api/logout")

    second_email = f"other-{unique_email}"
    second = client.post(
        "/api/register",
        json={
            "email": second_email,
            "password": "StrongPass123!",
            "guardian_confirmed": True,
        },
    )
    assert second.status_code == 200
    forbidden = client.get(f"/api/rewards?student_id={other_learner}")
    assert forbidden.status_code == 404


def test_successful_review_returns_immediate_effort_xp_and_gift_points(
    authenticated_client, app_module, monkeypatch
) -> None:
    monkeypatch.setattr(
        app_module,
        "review_homework",
        lambda *args, **kwargs: {
            "success": True,
            "review": "Good effort!",
            "score": 0,
            "max_score": 1,
        },
    )
    payload = {
        "homework": "What is 2 + 2?",
        "answers": "I tried 5",
        "subject": "Maths",
        "profile": {"year_group": 3, "age": 7},
        "quick_review": True,
    }
    first = authenticated_client.post("/api/review", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["reward_update"]["awarded_xp"] >= 20
    assert first.json()["reward_update"]["awarded_gift_points"] >= 20
    assert first.json()["reward_update"]["gift_points_eligible"] is True

    dashboard = authenticated_client.get("/api/rewards")
    assert dashboard.status_code == 200
    assert dashboard.json()["gift_access"]["eligible"] is True
    assert dashboard.json()["wallet"]["lifetime_xp"] >= 20
    assert dashboard.json()["wallet"]["gift_points"] >= 20

    repeated = authenticated_client.post("/api/review", json=payload)
    assert repeated.status_code == 200
    assert repeated.json()["reward_update"]["awarded_xp"] == 0
    assert repeated.json()["reward_update"]["already_awarded"] is True


def test_registered_account_review_earns_both_xp_and_gift_points(
    authenticated_client, app_module, monkeypatch
) -> None:
    monkeypatch.setattr(
        app_module,
        "review_homework",
        lambda *args, **kwargs: {
            "success": True,
            "review": "Good effort!",
            "score": 0,
            "max_score": 1,
        },
    )

    response = authenticated_client.post(
        "/api/review",
        json={
            "homework": "Which number is one more than 8?",
            "answers": "I think it is 9",
            "subject": "Maths",
            "profile": {"year_group": 2, "age": 6},
            "quick_review": True,
        },
    )

    assert response.status_code == 200, response.text
    reward = response.json()["reward_update"]
    assert reward["awarded_xp"] >= 20
    assert reward["awarded_gift_points"] == reward["awarded_xp"]
    assert reward["gift_points_eligible"] is True
    dashboard = authenticated_client.get("/api/rewards").json()
    assert dashboard["gift_access"]["eligible"] is True
    assert dashboard["wallet"]["gift_points"] >= reward["awarded_gift_points"]


def test_subscription_lookup_failure_keeps_xp_available_and_locks_gifts(
    authenticated_client, app_module, monkeypatch
) -> None:
    from src.webapp import account_store, reward_routes

    def unavailable(_account_id):
        raise RuntimeError("temporary subscription store failure")

    monkeypatch.setattr(
        account_store,
        "account_has_active_reward_subscription",
        unavailable,
    )
    monkeypatch.setattr(
        reward_routes,
        "account_has_active_reward_subscription",
        unavailable,
    )
    monkeypatch.setattr(
        app_module,
        "review_homework",
        lambda *args, **kwargs: {
            "success": True,
            "review": "Good effort!",
            "score": 1,
            "max_score": 1,
        },
    )

    reviewed = authenticated_client.post(
        "/api/review",
        json={
            "homework": "Write the number after 4.",
            "answers": "5",
            "subject": "Maths",
            "profile": {"year_group": 1, "age": 5},
            "quick_review": True,
        },
    )

    assert reviewed.status_code == 200, reviewed.text
    reward = reviewed.json()["reward_update"]
    assert reward["awarded_xp"] >= 20
    assert reward["awarded_gift_points"] == 0
    dashboard = authenticated_client.get("/api/rewards")
    assert dashboard.status_code == 200
    assert dashboard.json()["gift_access"]["eligible"] is False
