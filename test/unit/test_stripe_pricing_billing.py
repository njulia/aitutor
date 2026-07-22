from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


try:
    from src.webapp import stripe_pricing_billing as billing
except ModuleNotFoundError:
    # Allow this changed-files bundle to be tested before its files are copied
    # into their final project paths.
    MODULE_PATH = Path(__file__).with_name("stripe_pricing_billing.py")
    SPEC = importlib.util.spec_from_file_location(
        "stripe_pricing_billing_under_test", MODULE_PATH
    )
    assert SPEC and SPEC.loader
    billing = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(billing)


class StripeObject(dict):
    __getattr__ = dict.__getitem__


class FakeStripe:
    event = None
    subscription = None

    class Customer:
        @staticmethod
        def create(**kwargs):
            assert kwargs["email"] == "parent@example.com"
            assert kwargs["metadata"]["service"] == "Homework Magic"
            assert kwargs["idempotency_key"].startswith("homework-magic-customer-acct_")
            return StripeObject(id="cus_parent")

    class CustomerSession:
        @staticmethod
        def create(**kwargs):
            assert kwargs == {
                "customer": "cus_parent",
                "components": {"pricing_table": {"enabled": True}},
            }
            return StripeObject(client_secret="cuss_live_short_lived")

    class Subscription:
        @classmethod
        def retrieve(cls, subscription_id):
            assert subscription_id == "sub_parent"
            return FakeStripe.subscription

    class Webhook:
        @staticmethod
        def construct_event(payload, signature, secret):
            assert payload == b"signed payload"
            assert signature == "timestamp.signature"
            assert secret == "whsec_example"
            return FakeStripe.event

    class billing_portal:
        class Session:
            @staticmethod
            def create(**kwargs):
                assert kwargs["customer"] == "cus_parent"
                assert kwargs["return_url"] == "https://homeworkmagic.co.uk/pricing"
                return StripeObject(url="https://billing.stripe.com/p/session")


@pytest.fixture(autouse=True)
def isolated_billing_database(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'billing-test.db'}"
    )
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_example")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", billing.DEFAULT_PUBLISHABLE_KEY)
    monkeypatch.setenv("STRIPE_PRICING_TABLE_ID", billing.DEFAULT_PRICING_TABLE_ID)
    monkeypatch.setenv("APP_BASE_URL", "https://homeworkmagic.co.uk")
    monkeypatch.delenv("DEV_MODE", raising=False)
    monkeypatch.setattr(billing, "_billing_engine", None)
    monkeypatch.setattr(billing, "_billing_engine_url", None)
    monkeypatch.setattr(billing, "_stripe", lambda: FakeStripe)
    FakeStripe.event = None
    FakeStripe.subscription = None


def subscription(status="active"):
    period_end = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
    return StripeObject(
        id="sub_parent",
        customer="cus_parent",
        status=status,
        current_period_end=period_end,
        cancel_at_period_end=False,
        items=StripeObject(
            data=[
                StripeObject(
                    price=StripeObject(id="price_homework", product="prod_homework"),
                    current_period_end=period_end,
                )
            ]
        ),
    )


def event(event_type, event_object, livemode=True):
    return StripeObject(
        id="evt_example",
        type=event_type,
        livemode=livemode,
        data=StripeObject(object=event_object),
    )


def test_pricing_table_session_uses_authenticated_customer_session():
    result = billing.create_pricing_table_session("Parent@Example.com")

    assert result["client_secret"] == "cuss_live_short_lived"
    assert result["account_ref"].startswith("acct_")
    assert result["pricing_table_id"] == billing.DEFAULT_PRICING_TABLE_ID
    assert result["publishable_key"] == billing.DEFAULT_PUBLISHABLE_KEY
    assert not billing.billing_account_has_active_subscription("parent@example.com")


def test_signed_subscription_events_grant_then_revoke_access():
    billing.create_pricing_table_session("parent@example.com")
    FakeStripe.subscription = subscription("active")
    FakeStripe.event = event("customer.subscription.created", FakeStripe.subscription)

    assert billing.process_stripe_webhook(b"signed payload", "timestamp.signature") == "processed"
    assert billing.billing_account_has_active_subscription("parent@example.com")

    FakeStripe.subscription = subscription("canceled")
    FakeStripe.event = event("customer.subscription.deleted", FakeStripe.subscription)
    assert billing.process_stripe_webhook(b"signed payload", "timestamp.signature") == "processed"
    assert not billing.billing_account_has_active_subscription("parent@example.com")


def test_checkout_completion_reconciles_client_reference_id():
    context = billing.create_pricing_table_session("parent@example.com")
    FakeStripe.subscription = subscription("active")
    checkout_session = StripeObject(
        id="cs_live_example",
        customer="cus_parent",
        subscription="sub_parent",
        client_reference_id=context["account_ref"],
    )
    FakeStripe.event = event("checkout.session.completed", checkout_session)

    assert billing.process_stripe_webhook(b"signed payload", "timestamp.signature") == "processed"
    assert billing.billing_account_has_active_subscription("parent@example.com")


def test_wrong_mode_webhook_fails_closed():
    billing.create_pricing_table_session("parent@example.com")
    FakeStripe.event = event("customer.subscription.created", subscription(), livemode=False)

    with pytest.raises(ValueError, match="mode does not match"):
        billing.process_stripe_webhook(b"signed payload", "timestamp.signature")


def test_existing_subscription_is_sent_to_portal_not_duplicate_checkout():
    billing.create_pricing_table_session("parent@example.com")
    FakeStripe.event = event("customer.subscription.created", subscription())
    billing.process_stripe_webhook(b"signed payload", "timestamp.signature")

    with pytest.raises(ValueError, match="already has an active plan"):
        billing.create_pricing_table_session("parent@example.com")
    assert billing.create_customer_portal("parent@example.com").startswith(
        "https://billing.stripe.com/"
    )


def test_pricing_page_contains_only_public_stripe_identifiers():
    project_page = Path(__file__).resolve().parents[2] / "static" / "pricing.html"
    page_path = project_page if project_page.is_file() else Path(__file__).with_name("pricing.html")
    page = page_path.read_text(encoding="utf-8")

    assert billing.DEFAULT_PRICING_TABLE_ID in page
    assert billing.DEFAULT_PUBLISHABLE_KEY in page
    assert "customer-session-client-secret" in page
    assert "client-reference-id" in page
    assert "sk_live_" not in page
    assert "whsec_" not in page
