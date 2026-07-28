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
    portal_configurations = []
    portal_sessions = []

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

    class Price:
        @staticmethod
        def retrieve(price_id):
            products = {
                "price_homework": "prod_homework",
                "price_elevenplus": "prod_elevenplus",
            }
            return StripeObject(
                id=price_id,
                product=products[price_id],
                active=True,
                recurring=StripeObject(interval="month"),
            )

    class Webhook:
        @staticmethod
        def construct_event(payload, signature, secret):
            assert payload == b"signed payload"
            assert signature == "timestamp.signature"
            assert secret == "whsec_example"
            return FakeStripe.event

    class billing_portal:
        class Configuration:
            @staticmethod
            def list(**kwargs):
                assert kwargs == {"limit": 100}
                return StripeObject(data=[])

            @staticmethod
            def create(**kwargs):
                FakeStripe.portal_configurations.append(kwargs)
                return StripeObject(id="bpc_homework_magic")

        class Session:
            @staticmethod
            def create(**kwargs):
                assert kwargs["customer"] == "cus_parent"
                assert kwargs["return_url"] == "https://homeworkmagic.co.uk/pricing?billing=returned"
                assert kwargs["configuration"] == "bpc_homework_magic"
                FakeStripe.portal_sessions.append(kwargs)
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
    monkeypatch.setenv("STRIPE_PRICE_HOMEWORK_MONTHLY", "price_homework")
    monkeypatch.setenv("STRIPE_PRICE_ELEVENPLUS_MONTHLY", "price_elevenplus")
    monkeypatch.delenv("STRIPE_PRICE_FAMILY_MONTHLY", raising=False)
    monkeypatch.delenv("STRIPE_PORTAL_CONFIGURATION_ID", raising=False)
    monkeypatch.delenv("DEV_MODE", raising=False)
    monkeypatch.setattr(billing, "_billing_engine", None)
    monkeypatch.setattr(billing, "_billing_engine_url", None)
    monkeypatch.setattr(billing, "_stripe", lambda: FakeStripe)
    billing._portal_configuration_cache.clear()
    FakeStripe.event = None
    FakeStripe.subscription = None
    FakeStripe.portal_configurations = []
    FakeStripe.portal_sessions = []


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
    configuration = FakeStripe.portal_configurations[0]
    assert configuration["features"]["subscription_cancel"]["enabled"] is True
    assert configuration["features"]["subscription_cancel"]["mode"] == "at_period_end"
    assert configuration["features"]["subscription_update"]["enabled"] is True
    assert configuration["features"]["subscription_update"]["default_allowed_updates"] == ["price"]
    assert {
        product["product"] for product in configuration["features"]["subscription_update"]["products"]
    } == {"prod_homework", "prod_elevenplus"}


def test_change_and_cancel_open_explicit_stripe_portal_flows():
    billing.create_pricing_table_session("parent@example.com")
    FakeStripe.event = event("customer.subscription.created", subscription())
    billing.process_stripe_webhook(b"signed payload", "timestamp.signature")

    billing.create_customer_portal("parent@example.com", "change")
    change_flow = FakeStripe.portal_sessions[-1]["flow_data"]
    assert change_flow["type"] == "subscription_update"
    assert change_flow["subscription_update"] == {"subscription": "sub_parent"}
    assert change_flow["after_completion"]["redirect"]["return_url"].endswith(
        "/pricing?billing=changed"
    )

    billing.create_customer_portal("parent@example.com", "cancel")
    cancel_flow = FakeStripe.portal_sessions[-1]["flow_data"]
    assert cancel_flow["type"] == "subscription_cancel"
    assert cancel_flow["subscription_cancel"] == {"subscription": "sub_parent"}
    assert cancel_flow["after_completion"]["redirect"]["return_url"].endswith(
        "/pricing?billing=cancelled"
    )


def test_pricing_page_uses_the_supplied_stripe_pricing_table_without_secrets():
    project_page = Path(__file__).resolve().parents[2] / "static" / "pricing.html"
    page_path = project_page if project_page.is_file() else Path(__file__).with_name("pricing.html")
    page = page_path.read_text(encoding="utf-8")

    assert "/api/billing/status" in page
    assert "/api/billing/pricing-table-session" in page
    assert "/api/billing/checkout" in page  # Retained only for the one-off pass.
    assert "JSON.stringify({plan: 'trial_5day'})" in page
    assert "JSON.stringify({plan})" not in page
    assert 'src="https://js.stripe.com/v3/pricing-table.js"' in page
    assert "<stripe-pricing-table" in page
    assert 'pricing-table-id="prctbl_1TvlP9A7C4P8kXJMSS8t4VRT"' in page
    assert 'publishable-key="pk_live_fYeIDSqsqYC6MDKau5eFsI0U"' in page
    assert "customer-session-client-secret" in page
    assert "client-reference-id" in page
    assert "sk_live_" not in page
    assert "whsec_" not in page
    assert 'id="change-plan-button"' in page
    assert 'id="cancel-plan-button"' in page
    assert "/api/billing/portal/change" not in page  # Built from a fixed allow-listed action.
    assert "openPortal('change')" in page
    assert "openPortal('cancel')" in page

    app_page = page_path.with_name("app.html")
    if app_page.is_file():
        assert 'id="billing-link"' in app_page.read_text(encoding="utf-8")
