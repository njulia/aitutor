from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.webapp import account_store
from src.webapp.account_store import adjust_student_for_academic_year

pytestmark = pytest.mark.unit


def test_manual_year_group_selection_on_2_september_is_not_auto_promoted() -> None:
    student = {
        "name": "Ava",
        "year_group": 3,
        "age": 8,
        "created_at": datetime(2025, 8, 20, tzinfo=UTC),
        "year_group_set_at": datetime(2026, 9, 2, tzinfo=UTC),
    }
    adjusted = adjust_student_for_academic_year(student)
    assert adjusted["year_group"] == 3
    assert adjusted["age"] == 8


def test_learning_summary_preferences_default_and_unsubscribe(tmp_path, monkeypatch) -> None:
    db = tmp_path / "accounts.db"
    monkeypatch.setenv("ACCOUNT_DB_PATH", str(db))
    monkeypatch.delenv("ACCOUNT_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # This module keeps an engine cache; reload gives the test an isolated DB.
    import importlib
    mod = importlib.reload(account_store)
    account = mod.ensure_account("parent@example.com")
    prefs = mod.get_learning_summary_preferences(account["id"])
    assert prefs["enabled"] is True
    assert prefs["frequency"] == "weekly"
    assert prefs["interval_days"] == 7

    disabled = mod.set_learning_summary_preferences(
        account["id"], enabled=False, frequency="weekly", interval_days=7
    )
    assert disabled["enabled"] is False
    assert disabled["next_send_at"] is None

    enabled = mod.set_learning_summary_preferences(
        account["id"], enabled=True, frequency="custom", interval_days=14
    )
    assert enabled["enabled"] is True
    assert enabled["frequency"] == "custom"
    assert enabled["interval_days"] == 14


def test_learning_summary_email_uses_branded_sender_and_all_four_columns(monkeypatch) -> None:
    from src.webapp import email_service

    class FakeSMTP:
        messages = []
        def __init__(self, host, port, timeout): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def ehlo(self): return None
        def starttls(self, context): pass
        def login(self, username, password): pass
        def send_message(self, message): self.messages.append(message)

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_FROM", "Wrong <wrong@example.com>")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)

    status, error = email_service.send_xp_digest_email(
        to_email="parent@example.com",
        digest={"kids": [{
            "name": "Ava", "total_xp": 30, "event_count": 2,
            "subjects": [{"subject": "Maths", "accuracy": 90}],
        }]},
    )
    assert (status, error) == ("sent", None)
    message = FakeSMTP.messages[-1]
    assert message["From"] == "info@homeworkmagic.co.uk"
    assert "Child | XP earned | Activities | Subjects" in message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Subjects" in html
    assert "Maths 90%" in html


def test_target_summary_is_sent_once_when_daily_goal_is_reached(monkeypatch) -> None:
    from src.webapp import parent_dashboard_routes as routes

    sent = []
    monkeypatch.setattr(routes, "get_learning_summary_preferences", lambda account_id: {"enabled": True})
    monkeypatch.setattr(routes, "get_learning_target", lambda student_id: {"daily_goal": 2})
    monkeypatch.setattr(routes.get_reward_store(), "get_daily_activity_count", lambda **kwargs: 2)
    monkeypatch.setattr(routes, "claim_learning_summary_target_notification", lambda *args: True)
    monkeypatch.setattr(routes, "build_learning_summary_digest", lambda account_id: {"kids": [{"name": "Ava", "total_xp": 40, "event_count": 2, "subjects": []}]})
    monkeypatch.setattr(routes, "get_account", lambda account_id: {"email": "parent@example.com"})
    monkeypatch.setattr(routes, "send_target_learning_summary_if_reached", routes.send_target_learning_summary_if_reached)

    import src.webapp.email_service as email_service
    monkeypatch.setattr(email_service, "send_xp_digest_email", lambda **kwargs: sent.append(kwargs) or ("sent", None))

    routes.send_target_learning_summary_if_reached("acct_test", "stu_test")
    assert len(sent) == 1
    assert sent[0]["to_email"] == "parent@example.com"
