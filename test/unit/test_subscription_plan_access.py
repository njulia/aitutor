"""Plan-specific access and five-day paid trial tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.webapp import account_store, billing


def test_required_plan_names_are_clear(app_module) -> None:
    assert app_module._required_premium_plan(is_eleven_plus=False) == "homework_monthly"
    assert app_module._required_premium_plan(is_eleven_plus=True) == "elevenplus_monthly"
    homework_response = app_module._subscription_required_response(
        "Explain in Detail", "homework_monthly", "parent@example.com"
    )
    eleven_response = app_module._subscription_required_response(
        "Review Question", "elevenplus_monthly", "parent@example.com"
    )
    assert b"Homework Premium" in homework_response.body
    assert b"11+ Premium" in eleven_response.body


def test_plan_specific_access_and_trial_superset(monkeypatch) -> None:
    monkeypatch.setattr(account_store, "get_account_by_email", lambda _email: {"id": "acct_1"})

    monkeypatch.setattr(
        account_store,
        "get_active_subscription",
        lambda _account_id: {"plan": "homework_monthly"},
    )
    assert account_store.account_has_active_subscription(
        "parent@example.com", ["homework_monthly"]
    )
    assert not account_store.account_has_active_subscription(
        "parent@example.com", ["elevenplus_monthly"]
    )

    monkeypatch.setattr(
        account_store,
        "get_active_subscription",
        lambda _account_id: {"plan": "trial_5day"},
    )
    assert account_store.account_has_active_subscription(
        "parent@example.com", ["homework_monthly"]
    )
    assert account_store.account_has_active_subscription(
        "parent@example.com", ["elevenplus_monthly"]
    )


def test_trial_checkout_is_one_time_and_non_renewing(monkeypatch) -> None:
    captured = {}

    class FakeSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(url="https://checkout.test/trial", id="cs_trial")

    fake_stripe = SimpleNamespace(checkout=SimpleNamespace(Session=FakeSession))
    monkeypatch.setenv("STRIPE_PRICE_TRIAL_5DAY", "price_trial")
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setattr(billing, "get_active_subscription", lambda _account_id: None)
    monkeypatch.setattr(billing, "account_has_used_plan", lambda _account_id, _plan: False)

    result = billing.create_checkout(
        {"id": "acct_1", "email": "parent@example.com", "stripe_customer_id": "cus_1"},
        billing.TRIAL_PLAN,
    )

    assert result["checkout_session_id"] == "cs_trial"
    assert captured["mode"] == "payment"
    assert captured["line_items"] == [{"price": "price_trial", "quantity": 1}]
    assert "subscription_data" not in captured
    assert captured["allow_promotion_codes"] is False


def test_trial_can_only_be_started_once(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_PRICE_TRIAL_5DAY", "price_trial")
    monkeypatch.setattr(billing, "get_active_subscription", lambda _account_id: None)
    monkeypatch.setattr(billing, "account_has_used_plan", lambda _account_id, _plan: True)

    with pytest.raises(ValueError, match="already been used"):
        billing.create_checkout(
            {"id": "acct_1", "email": "parent@example.com", "stripe_customer_id": "cus_1"},
            billing.TRIAL_PLAN,
        )


def test_paid_trial_webhook_grants_five_days(monkeypatch) -> None:
    captured = {}
    monkeypatch.setenv("STRIPE_PRICE_TRIAL_5DAY", "price_trial")
    monkeypatch.setattr(
        billing,
        "upsert_stripe_subscription",
        lambda **kwargs: captured.update(kwargs) or kwargs,
    )

    before = datetime.now(UTC)
    billing.sync_trial_checkout({
        "id": "cs_paid",
        "client_reference_id": "acct_1",
        "customer": "cus_1",
        "payment_status": "paid",
        "metadata": {"account_id": "acct_1", "plan": billing.TRIAL_PLAN},
    })

    assert captured["plan"] == billing.TRIAL_PLAN
    assert captured["status"] == "active"
    assert captured["cancel_at_period_end"] is True
    assert before + timedelta(days=5) <= captured["current_period_end"] <= datetime.now(UTC) + timedelta(days=5)
