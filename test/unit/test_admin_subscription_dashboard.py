from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from src.admin import get_subscription_overview
from src.webapp import account_store, billing


def test_subscription_overview_includes_parent_and_elevenplus_plan(
    unique_email,
) -> None:
    account = account_store.ensure_account(
        unique_email,
        display_name="Parent Tester",
    )
    subscription = account_store.create_subscription(
        account_id=account["id"],
        plan="elevenplus_monthly",
        status="active",
        duration_days=31,
        stripe_customer_id=f"cus_{account['id'][-12:]}",
        stripe_subscription_id=f"sub_{account['id'][-12:]}",
    )

    overview = get_subscription_overview()
    saved = next(
        item
        for item in overview["subscriptions"]
        if item["id"] == subscription["id"]
    )

    assert saved["customer_email"] == unique_email
    assert saved["customer_name"] == "Parent Tester"
    assert saved["plan"] == "elevenplus_monthly"
    assert overview["active_by_plan"]["elevenplus_monthly"] >= 1
    assert overview["estimated_revenue_gbp"] >= 9.99


def test_admin_stripe_refresh_recovers_missed_elevenplus_webhook(
    monkeypatch,
    unique_email,
) -> None:
    monkeypatch.setenv("STRIPE_BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_admin_refresh")
    monkeypatch.setenv(
        "STRIPE_PRICE_ELEVENPLUS_MONTHLY",
        "price_elevenplus_admin",
    )
    account = account_store.ensure_account(unique_email)
    customer_id = f"cus_{account['id'][-12:]}"
    account_store.set_stripe_customer(account["id"], customer_id)
    period_end = datetime.now(UTC) + timedelta(days=30)
    captured = {}

    stripe_subscription = SimpleNamespace(
        id=f"sub_{account['id'][-12:]}",
        customer=customer_id,
        metadata={},
        status="active",
        current_period_end=int(period_end.timestamp()),
        cancel_at_period_end=False,
        items=SimpleNamespace(
            data=[
                SimpleNamespace(
                    price=SimpleNamespace(id="price_elevenplus_admin"),
                    current_period_end=int(period_end.timestamp()),
                )
            ]
        ),
    )

    class FakeSubscription:
        @staticmethod
        def list(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                data=[stripe_subscription],
                has_more=False,
            )

    monkeypatch.setattr(
        billing,
        "_stripe",
        lambda: SimpleNamespace(Subscription=FakeSubscription),
    )
    monkeypatch.setattr(
        billing,
        "_record_subscription_transition",
        lambda _previous, _current: None,
    )

    result = billing.refresh_stripe_subscription_catalog()
    saved = account_store.get_subscription_by_stripe_id(
        stripe_subscription.id
    )

    assert captured == {"status": "all", "limit": 100}
    assert result == {
        "attempted": True,
        "succeeded": True,
        "received": 1,
        "synced": 1,
        "skipped": 0,
        "has_more": False,
    }
    assert saved is not None
    assert saved["account_id"] == account["id"]
    assert saved["plan"] == "elevenplus_monthly"
    assert saved["status"] == "active"


def test_admin_refresh_recovers_discounted_pricing_table_subscription(
    monkeypatch,
    unique_email,
) -> None:
    """A discount must not hide a subscription created with a newer Price."""
    monkeypatch.setenv("STRIPE_BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_EXPECTED_LIVEMODE", "false")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_admin_refresh")
    monkeypatch.setenv(
        "STRIPE_PRICE_ELEVENPLUS_MONTHLY",
        "price_previous_elevenplus",
    )
    account = account_store.ensure_account(unique_email)
    period_end = datetime.now(UTC) + timedelta(days=30)
    stripe_subscription = SimpleNamespace(
        id=f"sub_discount_{account['id'][-10:]}",
        customer=f"cus_discount_{account['id'][-10:]}",
        metadata={},
        status="active",
        cancel_at_period_end=False,
        discounts=[SimpleNamespace(promotion_code="promo_parent_test")],
        items=SimpleNamespace(
            data=[
                SimpleNamespace(
                    price=SimpleNamespace(id="price_current_elevenplus"),
                    current_period_end=int(period_end.timestamp()),
                )
            ]
        ),
    )
    checkout_session = SimpleNamespace(
        id="cs_discount",
        status="complete",
        mode="subscription",
        client_reference_id=account["id"],
        customer=stripe_subscription.customer,
        subscription=stripe_subscription.id,
    )

    class FakeSubscription:
        @staticmethod
        def list(**_kwargs):
            return SimpleNamespace(data=[stripe_subscription], has_more=False)

        @staticmethod
        def retrieve(_subscription_id):
            return stripe_subscription

    class FakeCheckoutSession:
        @staticmethod
        def list(**kwargs):
            assert kwargs == {
                "subscription": stripe_subscription.id,
                "status": "complete",
                "limit": 10,
            }
            return SimpleNamespace(data=[checkout_session], has_more=False)

    class FakePrice:
        @staticmethod
        def retrieve(price_id, **kwargs):
            assert price_id == "price_current_elevenplus"
            assert kwargs == {"expand": ["product"]}
            return SimpleNamespace(
                id=price_id,
                active=True,
                livemode=False,
                currency="gbp",
                recurring=SimpleNamespace(interval="month"),
                lookup_key=None,
                metadata={},
                product=SimpleNamespace(
                    name="11+ Premium",
                    metadata={},
                ),
            )

    fake_stripe = SimpleNamespace(
        Subscription=FakeSubscription,
        Price=FakePrice,
        checkout=SimpleNamespace(Session=FakeCheckoutSession),
    )
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing,
        "_record_subscription_transition",
        lambda _previous, _current: None,
    )

    result = billing.refresh_stripe_subscription_catalog()
    saved = account_store.get_subscription_by_stripe_id(
        stripe_subscription.id
    )

    assert result["synced"] == 1
    assert result["skipped"] == 0
    assert saved is not None
    assert saved["account_id"] == account["id"]
    assert saved["stripe_customer_id"] == stripe_subscription.customer
    assert saved["price_id"] == "price_current_elevenplus"
    assert saved["plan"] == "elevenplus_monthly"


def test_admin_refresh_falls_back_to_completed_checkout_sessions(
    monkeypatch,
    unique_email,
) -> None:
    monkeypatch.setenv("STRIPE_BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_admin_refresh")
    monkeypatch.setenv(
        "STRIPE_PRICE_ELEVENPLUS_MONTHLY",
        "price_elevenplus_checkout_recovery",
    )
    account = account_store.ensure_account(unique_email)
    period_end = datetime.now(UTC) + timedelta(days=30)
    stripe_subscription = SimpleNamespace(
        id=f"sub_checkout_{account['id'][-10:]}",
        customer=f"cus_checkout_{account['id'][-10:]}",
        metadata={},
        status="active",
        cancel_at_period_end=False,
        items=SimpleNamespace(
            data=[
                SimpleNamespace(
                    price=SimpleNamespace(
                        id="price_elevenplus_checkout_recovery"
                    ),
                    current_period_end=int(period_end.timestamp()),
                )
            ]
        ),
    )
    checkout_session = SimpleNamespace(
        id="cs_checkout_recovery",
        status="complete",
        client_reference_id=account["id"],
        customer=stripe_subscription.customer,
        subscription=stripe_subscription.id,
    )

    class FakeSubscription:
        @staticmethod
        def list(**_kwargs):
            raise RuntimeError("subscription list unavailable")

        @staticmethod
        def retrieve(subscription_id):
            assert subscription_id == stripe_subscription.id
            return stripe_subscription

    class FakeCheckoutSession:
        @staticmethod
        def list(**kwargs):
            if "subscription" in kwargs:
                assert kwargs["subscription"] == stripe_subscription.id
            else:
                assert kwargs == {"status": "complete", "limit": 100}
            return SimpleNamespace(data=[checkout_session], has_more=False)

    fake_stripe = SimpleNamespace(
        Subscription=FakeSubscription,
        checkout=SimpleNamespace(Session=FakeCheckoutSession),
    )
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing,
        "_record_subscription_transition",
        lambda _previous, _current: None,
    )

    result = billing.refresh_stripe_subscription_catalog()

    assert result["source"] == "checkout_sessions"
    assert result["synced"] == 1
    assert account_store.get_active_subscription(account["id"]) is not None


def test_admin_subscription_page_refreshes_and_is_not_cached(
    admin_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        billing,
        "refresh_stripe_subscription_catalog",
        lambda _limit: {
            "attempted": True,
            "succeeded": True,
            "received": 1,
            "synced": 1,
            "skipped": 0,
            "has_more": False,
        },
    )

    response = admin_client.get("/api/admin/subscriptions")
    page = admin_client.get("/admin")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    assert response.json()["stripe_sync"]["synced"] == 1
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store, private"
    assert "11+ Premium" in page.text
    assert "Parent account" in page.text
    assert "Sync Stripe" in page.text


def test_admin_subscription_refresh_failure_keeps_saved_records(
    admin_client,
    monkeypatch,
) -> None:
    def fail_refresh(_limit):
        raise RuntimeError("temporary Stripe outage")

    monkeypatch.setattr(
        billing,
        "refresh_stripe_subscription_catalog",
        fail_refresh,
    )

    response = admin_client.get("/api/admin/subscriptions")

    assert response.status_code == 200
    assert response.json()["stripe_sync"] == {
        "attempted": True,
        "succeeded": False,
    }
    assert isinstance(response.json()["subscriptions"], list)
