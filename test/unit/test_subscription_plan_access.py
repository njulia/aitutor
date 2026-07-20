"""Plan-specific access and five-day paid trial tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.webapp import account_store, billing


def _configure_test_billing(monkeypatch, **prices) -> None:
    monkeypatch.setenv("STRIPE_BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_EXPECTED_LIVEMODE", "false")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_unit")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_unit")
    for name, value in prices.items():
        monkeypatch.setenv(name, value)


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
    _configure_test_billing(monkeypatch, STRIPE_PRICE_TRIAL_5DAY="price_trial")
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
    _configure_test_billing(monkeypatch, STRIPE_PRICE_TRIAL_5DAY="price_trial")
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


def test_active_checkout_queues_subscription_confirmation_for_parent(monkeypatch) -> None:
    period_end = datetime(2026, 8, 20, tzinfo=UTC)
    notifications = []
    monkeypatch.setattr(
        billing,
        "get_account",
        lambda account_id: {"id": account_id, "email": "parent@example.com"},
    )

    billing._queue_subscription_confirmation(
        {
            "account_id": "acct_1",
            "plan": "homework_monthly",
            "status": "active",
            "current_period_end": period_end,
        },
        notifications,
    )

    assert notifications == [{
        "to_email": "parent@example.com",
        "plan": "homework_monthly",
        "current_period_end": period_end,
    }]


def test_inactive_checkout_does_not_queue_subscription_confirmation(monkeypatch) -> None:
    notifications = []
    monkeypatch.setattr(
        billing,
        "get_account",
        lambda _account_id: pytest.fail("Inactive subscriptions must not resolve an email"),
    )

    billing._queue_subscription_confirmation(
        {"account_id": "acct_1", "plan": "homework_monthly", "status": "incomplete"},
        notifications,
    )

    assert notifications == []


def test_verified_checkout_webhook_collects_active_subscription_email(monkeypatch) -> None:
    finished = []

    class FakeLedger:
        def begin(self, event_id, event_type):
            assert (event_id, event_type) == ("evt_checkout", "checkout.session.completed")
            return True

        def finish(self, event_id, status):
            finished.append((event_id, status))

    subscription = {
        "account_id": "acct_1",
        "plan": "homework_monthly",
        "status": "active",
        "current_period_end": datetime(2026, 8, 20, tzinfo=UTC),
    }
    fake_stripe = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: {
            "id": "evt_checkout",
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {"object": {
                "subscription": "sub_1",
                "client_reference_id": "acct_1",
                "metadata": {"plan": "homework_monthly"},
            }},
        }),
        Subscription=SimpleNamespace(retrieve=lambda _subscription_id: {"id": "sub_1"}),
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_unit")
    monkeypatch.setenv("STRIPE_EXPECTED_LIVEMODE", "false")
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setattr(billing, "ledger", lambda: FakeLedger())
    monkeypatch.setattr(billing, "sync_subscription", lambda *_args, **_kwargs: subscription)
    monkeypatch.setattr(
        billing,
        "get_account",
        lambda _account_id: {"id": "acct_1", "email": "parent@example.com"},
    )
    notifications = []

    status = billing.process_webhook(b"signed payload", "signature", notifications)

    assert status == "processed"
    assert finished == [("evt_checkout", "processed")]
    assert notifications[0]["to_email"] == "parent@example.com"
    assert notifications[0]["plan"] == "homework_monthly"


def test_checkout_is_blocked_when_webhook_cannot_grant_access(monkeypatch) -> None:
    _configure_test_billing(
        monkeypatch,
        STRIPE_PRICE_HOMEWORK_MONTHLY="price_homework",
    )
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")

    assert "STRIPE_WEBHOOK_SECRET is not configured" in billing.billing_configuration_issues(
        "homework_monthly"
    )


def test_subscription_entitlement_is_bound_to_configured_price(monkeypatch) -> None:
    captured = {}
    _configure_test_billing(
        monkeypatch,
        STRIPE_PRICE_HOMEWORK_MONTHLY="price_homework",
        STRIPE_PRICE_ELEVENPLUS_MONTHLY="price_elevenplus",
    )
    monkeypatch.setattr(
        billing,
        "upsert_stripe_subscription",
        lambda **kwargs: captured.update(kwargs) or kwargs,
    )

    billing.sync_subscription({
        "id": "sub_1",
        "customer": "cus_1",
        "status": "active",
        "metadata": {"account_id": "acct_1", "plan": "homework_monthly"},
        "items": {
            "data": [{
                "price": {"id": "price_homework"},
                "current_period_end": 2_000_000_000,
            }]
        },
    })

    assert captured["plan"] == "homework_monthly"
    assert captured["price_id"] == "price_homework"
    assert captured["current_period_end"] == datetime.fromtimestamp(2_000_000_000, tz=UTC)


def test_subscription_rejects_metadata_price_mismatch(monkeypatch) -> None:
    _configure_test_billing(
        monkeypatch,
        STRIPE_PRICE_HOMEWORK_MONTHLY="price_homework",
        STRIPE_PRICE_ELEVENPLUS_MONTHLY="price_elevenplus",
    )

    with pytest.raises(ValueError, match="metadata does not match"):
        billing.sync_subscription({
            "id": "sub_1",
            "customer": "cus_1",
            "status": "active",
            "metadata": {"account_id": "acct_1", "plan": "elevenplus_monthly"},
            "items": {"data": [{"price": {"id": "price_homework"}}]},
        })


def test_live_checkout_verifies_price_before_opening_session(monkeypatch) -> None:
    captured = {"retrieved": []}

    class FakePrice:
        @staticmethod
        def retrieve(price_id):
            captured["retrieved"].append(price_id)
            return {
                "id": price_id,
                "active": True,
                "livemode": True,
                "currency": "gbp",
                "unit_amount": 499,
                "recurring": {"interval": "month"},
            }

    class FakeSession:
        @staticmethod
        def create(**kwargs):
            captured["checkout"] = kwargs
            return SimpleNamespace(url="https://checkout.stripe.test/live", id="cs_live")

    fake_stripe = SimpleNamespace(
        Price=FakePrice,
        checkout=SimpleNamespace(Session=FakeSession),
    )
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("APP_BASE_URL", "https://homework.example")
    monkeypatch.setenv("STRIPE_BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_EXPECTED_LIVEMODE", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_unit")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_live_unit")
    monkeypatch.setenv("STRIPE_PRICE_HOMEWORK_MONTHLY", "price_live_homework_unit")
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setattr(billing, "get_active_subscription", lambda _account_id: None)

    result = billing.create_checkout(
        {"id": "acct_live", "email": "parent@example.com", "stripe_customer_id": "cus_live"},
        "homework_monthly",
    )

    assert result["checkout_session_id"] == "cs_live"
    assert captured["retrieved"] == ["price_live_homework_unit"]
    assert captured["checkout"]["mode"] == "subscription"
