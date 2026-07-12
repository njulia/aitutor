from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.webapp.account_store as accounts
import src.webapp.billing as billing
import src.webapp.runtime as runtime
from src.webapp.memory_store import LearningMemoryStore


def reset_account_store(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'accounts.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    if accounts._ENGINE is not None:
        accounts._ENGINE.dispose()
    monkeypatch.setattr(accounts, "_ENGINE", None)
    monkeypatch.setattr(accounts, "_ENGINE_URL", None)
    return url


def test_webhook_materialised_subscription_drives_entitlement(tmp_path, monkeypatch):
    reset_account_store(tmp_path, monkeypatch)
    account = accounts.ensure_account("parent@example.com")
    subscription = {
        "id": "sub_123",
        "customer": "cus_123",
        "status": "active",
        "current_period_end": int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
        "cancel_at_period_end": False,
        "metadata": {"account_id": account["id"], "plan": "family_monthly"},
        "items": {"data": [{"price": {"id": "price_123"}}]},
    }
    stored = billing.sync_subscription(subscription)
    assert stored["status"] == "active"
    assert accounts.account_has_active_subscription("parent@example.com") is True
    stats = accounts.get_subscription_stats()
    assert stats["active_subscriptions"] == 1
    assert stats["source"] == "local_webhook_materialisation"


def test_subscription_sync_contains_only_account_billing_fields(tmp_path, monkeypatch):
    reset_account_store(tmp_path, monkeypatch)
    account = accounts.ensure_account("parent@example.com")
    accounts.ensure_default_student(account["id"], "Star", 4, 8)
    stored = billing.sync_subscription({
        "id": "sub_safe",
        "customer": "cus_safe",
        "status": "trialing",
        "metadata": {"account_id": account["id"], "plan": "homework_monthly"},
        "items": {"data": [{"price": {"id": "price_safe"}}]},
    })
    assert "student_id" not in stored
    assert "learner_id" not in stored
    assert "homework_content" not in stored
    assert "name" not in stored


def test_memory_full_erasure_removes_settings_and_preferences(tmp_path):
    store = LearningMemoryStore(f"sqlite+pysqlite:///{tmp_path / 'memory.db'}")
    store.update_settings("stu", "acct", enabled=True)
    store.update_preferences("stu", "acct", explanation_style="worked_example", hint_style="small_hint")
    store.record_event(student_id="stu", account_id="acct", subject="Maths", topic="Fractions", outcome=0.5)
    assert store.delete_all("stu", "acct", include_preferences=True) == 1
    summary = store.summary("stu", "acct")
    assert summary["settings"]["enabled"] is False
    assert summary["preferences"]["explanation_style"] == "short_steps"
    assert summary["recent_events"] == []


def test_production_requires_postgresql(monkeypatch):
    original = runtime.settings
    monkeypatch.setattr(runtime, "settings", replace(original, dev_mode=False))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        runtime.validate_database_configuration()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///bad.db")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        runtime.validate_database_configuration()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/app")
    runtime.validate_database_configuration()


def test_cross_site_browser_write_is_blocked(monkeypatch):
    app = FastAPI()
    app.add_middleware(runtime.SameOriginWriteMiddleware)

    @app.post("/change")
    async def change():
        return {"ok": True}

    client = TestClient(app, base_url="http://testserver")
    assert client.post("/change", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/change", headers={"Origin": "http://testserver"}).status_code == 200
    assert client.post("/change").status_code == 200
