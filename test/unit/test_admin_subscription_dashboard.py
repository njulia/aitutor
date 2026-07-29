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
