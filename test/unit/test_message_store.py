from src.webapp.message_store import MessageStore


def test_create_list_reply_and_status(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    created = store.create_message(
        user_id="parent@example.com",
        user_email="Parent@Example.com",
        subject="Need help",
        category="homework",
        message="Please help with this question.",
    )
    assert created["status"] == "open"
    assert created["user_email"] == "parent@example.com"
    assert created["access_token"]

    user_items = store.list_for_user(email="parent@example.com")
    assert [item["id"] for item in user_items] == [created["id"]]

    replied = store.add_reply(
        message_id=created["id"],
        admin_name="Support",
        reply="Here is the answer.",
        email_status="sent",
    )
    assert replied["status"] == "replied"
    assert replied["replies"][0]["reply"] == "Here is the answer."
    assert replied["replies"][0]["email_status"] == "sent"

    closed = store.update_status(created["id"], "closed")
    assert closed["status"] == "closed"


def test_anonymous_access_token_controls_access(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    item = store.create_message(
        user_id=None,
        user_email="anon@example.com",
        subject="Question",
        category="general",
        message="A private message",
    )
    assert store.get_for_user(item["id"], email=None, access_token="wrong") is None
    allowed = store.get_for_user(item["id"], email=None, access_token=item["access_token"])
    assert allowed["message"] == "A private message"
