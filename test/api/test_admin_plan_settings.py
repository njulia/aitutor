from __future__ import annotations

from types import SimpleNamespace

from src.webapp import account_store
from src.webapp import billing


def test_admin_can_change_a_plan_child_limit_and_public_catalog_reflects_it(
    admin_client,
    client,
    unique_email,
) -> None:
    plan = account_store.SCHOOL_HOMEWORK_PREMIUM_PLAN
    original = account_store.get_plan_settings(plan)
    account = account_store.ensure_account(unique_email)
    account_store.create_subscription(
        account_id=account["id"],
        plan=plan,
        status="active",
        duration_days=30,
    )
    try:
        # The shared TestClient is signed in by the admin fixture; clear that
        # session before proving the endpoint rejects an ordinary visitor.
        client.post("/api/logout")
        denied = client.put(
            f"/api/admin/plan-settings/{plan}",
            json={"price_pence": original["price_pence"], "max_students": 7},
        )
        admin_login = admin_client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "StrongPass123!"},
        )
        response = admin_client.put(
            f"/api/admin/plan-settings/{plan}",
            json={"price_pence": original["price_pence"], "max_students": 7},
        )
        catalog = client.get("/api/billing/plans")

        assert denied.status_code in {401, 403}
        assert admin_login.status_code == 200
        assert response.status_code == 200, response.text
        assert response.json()["plan"]["max_students"] == 7
        assert account_store.get_student_limit(account["id"]) == 7
        assert catalog.status_code == 200
        public_plan = next(item for item in catalog.json()["plans"] if item["plan"] == plan)
        assert public_plan["max_children"] == 7
        assert "price_pence" in public_plan
    finally:
        account_store.save_plan_settings(
            plan,
            price_pence=original["price_pence"],
            max_students=original["max_students"],
            stripe_price_id=original["stripe_price_id"],
        )


def test_price_change_creates_a_new_stripe_price_and_preserves_existing_plan_setting(
    monkeypatch,
) -> None:
    plan = account_store.HOMEWORK_PREMIUM_PLAN
    original = account_store.get_plan_settings(plan)
    events: list[tuple[str, object]] = []

    class FakePrice:
        @staticmethod
        def retrieve(price_id):
            events.append(("retrieve", price_id))
            return SimpleNamespace(
                id=price_id,
                currency="gbp",
                recurring={"interval": "month"},
                product="prod_homework",
                metadata={},
                tax_behavior="unspecified",
            )

        @staticmethod
        def create(**kwargs):
            events.append(("create", kwargs))
            return SimpleNamespace(id="price_replacement")

        @staticmethod
        def modify(price_id, **kwargs):
            events.append(("modify", (price_id, kwargs)))

    monkeypatch.setattr(billing, "_billing_enabled", lambda: True)
    monkeypatch.setattr(billing, "_stripe", lambda: SimpleNamespace(Price=FakePrice))
    monkeypatch.setattr(billing, "_plans", lambda: {plan: "price_existing"})
    try:
        saved = billing.update_paid_plan_settings(
            plan,
            price_pence=749,
            max_students=3,
        )

        assert saved["price_pence"] == 749
        assert saved["max_students"] == 3
        assert saved["stripe_price_id"] == "price_replacement"
        assert ("retrieve", "price_existing") in events
        create = next(value for name, value in events if name == "create")
        assert create["unit_amount"] == 749
        assert create["recurring"] == {"interval": "month"}
        assert ("modify", ("price_existing", {"active": False})) in events
        assert account_store.historical_plan_for_price("price_existing") == plan
    finally:
        account_store.save_plan_settings(
            plan,
            price_pence=original["price_pence"],
            max_students=original["max_students"],
            stripe_price_id=original["stripe_price_id"],
        )
