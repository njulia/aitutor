from __future__ import annotations

from datetime import UTC, datetime

from src.admin import create_admin_subscription, subscription_duration_days
from src.webapp import account_store
from src.progress_db import get_user_by_username, is_user_test


def test_admin_can_create_test_subscription_without_stripe(admin_client, unique_email, monkeypatch):
    def fail_stripe(*_args, **_kwargs):
        raise AssertionError("Admin test subscriptions must not call Stripe")

    monkeypatch.setattr("src.webapp.billing._stripe", fail_stripe)
    response = admin_client.post(
        "/api/admin/subscriptions",
        json={
            "email": unique_email,
            "name": "Test Parent",
            "plan": "school_homework_monthly",
            "duration": "months",
            "months": 3,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["subscription"]["stripe_charged"] is False
    saved = account_store.get_active_subscription(
        account_store.get_account_by_email(unique_email)["id"]
    )
    assert saved["plan"] == "school_homework_monthly"
    assert saved["status"] == "active"
    assert saved["stripe_subscription_id"].startswith("manual_")


def test_admin_test_subscription_requires_admin(admin_client, unique_email):
    # A non-admin authenticated user must not be able to grant entitlements.
    from fastapi.testclient import TestClient
    from web_app import app

    other = TestClient(app, base_url="http://testserver")
    other.post("/api/register", json={"email": unique_email, "password": "StrongPass123!"})
    response = other.post(
        "/api/admin/subscriptions",
        json={
            "email": unique_email,
            "name": "Nope",
            "plan": "homework_monthly",
            "duration": "5_days",
        },
    )
    assert response.status_code == 403


def test_custom_month_duration_uses_calendar_month():
    start = datetime(2026, 1, 31, tzinfo=UTC)
    # Jan 31 -> Feb 28 is one calendar-month boundary.
    assert subscription_duration_days("1_month", start) == 28
    assert subscription_duration_days("months", start, 2) == 59


def test_mark_test_bypasses_subscription_checks_until_unmarked(admin_client, unique_email):
    from fastapi.testclient import TestClient
    from web_app import app
    target = TestClient(app, base_url="http://testserver")
    target.post("/api/register", json={"email": unique_email, "password": "StrongPass123!"})
    admin = TestClient(app, base_url="http://testserver")
    admin.post("/api/login", json={"email": "admin@example.com", "password": "StrongPass123!"})
    response = admin.post(
        f"/api/admin/users/{unique_email}/test-toggle?enable=true"
    )
    assert response.status_code == 200
    assert is_user_test(unique_email) is True

    # The central entitlement checks used by the app must grant access even
    # without any paid/local subscription.
    assert account_store.account_has_active_subscription(unique_email, required_plans=["elevenplus_monthly"]) is True

    response = admin.post(
        f"/api/admin/users/{unique_email}/test-toggle?enable=false"
    )
    assert response.status_code == 200
    assert is_user_test(unique_email) is False
    assert account_store.account_has_active_subscription(unique_email, required_plans=["elevenplus_monthly"]) is False
