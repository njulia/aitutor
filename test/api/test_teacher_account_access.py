from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from test.conftest import register_or_login

pytestmark = pytest.mark.api


def _grant_school_plan(email: str) -> None:
    from src.webapp.account_store import get_account_by_email, upsert_stripe_subscription

    account = get_account_by_email(email)
    assert account is not None
    upsert_stripe_subscription(
        account_id=account["id"],
        plan="school_homework_monthly",
        status="active",
        stripe_customer_id=f"cus_{email.split("@")[0]}",
        stripe_subscription_id=f"sub_{email.split("@")[0]}",
        price_id="price_school_teacher",
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        cancel_at_period_end=False,
    )


def test_school_teacher_uses_shared_dashboard_and_teacher_session_role(client, unique_email) -> None:
    register_or_login(client, unique_email)
    _grant_school_plan(unique_email)

    context = client.get("/api/session-context")
    assert context.status_code == 200, context.text
    data = context.json()
    assert data["authenticated"] is True
    assert data["role"] == "teacher"
    assert len(data["students"]) == 1

    dashboard = client.get("/parent-dashboard")
    assert dashboard.status_code == 200


def test_school_teacher_login_redirects_to_shared_dashboard(client, unique_email) -> None:
    register_or_login(client, unique_email)
    _grant_school_plan(unique_email)
    assert client.post("/api/logout").status_code == 200

    response = client.post("/api/login", json={
        "email": unique_email,
        "password": "StrongPass123!",
    })
    assert response.status_code == 200

    # The API login stays JSON; the browser login.js uses the teacher flag from
    # check-parent-status to route the teacher to the shared dashboard.
    status = client.get("/api/check-parent-status")
    assert status.status_code == 200
    assert status.json()["is_teacher"] is True


def test_teacher_dashboard_frontend_accepts_teacher_role() -> None:
    from pathlib import Path

    script = Path("static/js/parent-dashboard.js").read_text(encoding="utf-8")
    assert "context.role !== 'parent' && context.role !== 'teacher'" in script


def test_pricing_table_config_does_not_require_every_checkout_price(monkeypatch):
    from src.webapp import billing

    monkeypatch.setenv("STRIPE_BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_example")
    monkeypatch.setenv("STRIPE_EXPECTED_LIVEMODE", "true")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_live_example")
    monkeypatch.setenv("STRIPE_PRICING_TABLE_ID", "prctbl_example")
    monkeypatch.delenv("STRIPE_PRICE_SCHOOL_HOMEWORK_MONTHLY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_HOMEWORK_MONTHLY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ELEVENPLUS_MONTHLY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_TRIAL_5DAY", raising=False)

    assert billing.pricing_table_configuration_issues() == []
