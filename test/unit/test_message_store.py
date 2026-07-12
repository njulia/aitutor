from pathlib import Path

from src.webapp.message_store import MessageStore


def test_message_reply_and_access(tmp_path: Path):
    store = MessageStore(str(tmp_path), db_path=str(tmp_path / "messages.db"))
    created, token = store.create_message(
        owner_id="anonymous:test-browser",
        contact_email="parent@example.com",
        category="homework",
        subject="Marking question",
        message="Please help with a marking problem.",
    )

    message_id = created["id"]
    assert store.get_for_user(message_id, "anonymous:test-browser")["subject"] == "Marking question"
    assert store.get_for_user(message_id, "anonymous:other", token)["id"] == message_id
    assert store.get_for_user(message_id, "anonymous:other", "wrong-token") is None

    reply = store.add_reply(
        message_id=message_id,
        reply="We have fixed this for you.",
        admin_email="admin@example.com",
        email_requested=True,
    )
    assert reply and reply["email_status"] == "pending"
    store.update_reply_delivery(reply["id"], "sent", None)

    user_view = store.get_for_user(message_id, "anonymous:test-browser")
    assert user_view["status"] == "replied"
    assert user_view["replies"][0]["reply"] == "We have fixed this for you."
    assert "admin_email" not in user_view["replies"][0]

    admin_view = store.get_for_admin(message_id)
    assert admin_view["contact_email"] == "parent@example.com"
    assert admin_view["replies"][0]["email_status"] == "sent"


def test_summary_and_status(tmp_path: Path):
    store = MessageStore(str(tmp_path), db_path=str(tmp_path / "messages.db"))
    created, _ = store.create_message(
        owner_id="account:parent@example.com",
        contact_email="parent@example.com",
        category="privacy",
        subject="Data question",
        message="How can I delete my data?",
    )
    assert store.summary()["open"] == 1
    assert store.update_status(created["id"], "closed") is True
    summary = store.summary()
    assert summary["open"] == 0
    assert summary["closed"] == 1
