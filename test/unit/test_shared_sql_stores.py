from __future__ import annotations

from pathlib import Path

from src.webapp.message_store import _SQLMessageStore
from src.webapp.password_reset_store import _SQLPasswordResetStore


def test_sql_message_store_contract_with_sqlite_engine(tmp_path: Path) -> None:
    store = _SQLMessageStore(f"sqlite+pysqlite:///{tmp_path / 'shared.db'}")
    created, token = store.create_message(
        owner_id="owner-a",
        contact_email="parent@example.com",
        category="privacy",
        subject="Data request",
        message="Please delete the learner profile.",
    )
    assert created["status"] == "open"
    assert store.get_for_user(created["id"], "other", token)["subject"] == "Data request"
    reply = store.add_reply(
        message_id=created["id"],
        reply="We have received the request.",
        admin_email="admin@example.com",
        email_requested=False,
    )
    assert reply is not None
    assert store.summary()["replied"] == 1
    assert store.delete_for_owners(["owner-a"]) == 1


def test_sql_password_reset_store_contract_with_sqlite_engine(tmp_path: Path) -> None:
    store = _SQLPasswordResetStore(f"sqlite+pysqlite:///{tmp_path / 'shared.db'}")
    assert store.record_request_if_allowed("parent@example.com", "client-a")
    token, _ = store.create_token("parent@example.com")
    assert store.is_valid(token)
    assert store.consume(token) == "parent@example.com"
    assert not store.is_valid(token)
