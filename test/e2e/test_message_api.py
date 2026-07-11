from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.webapp.message_routes import create_message_router
from src.webapp.message_store import MessageStore


def _identity(_request):
    return "parent@example.com", "parent@example.com", None


def test_user_submit_admin_reply_and_user_reads_reply(tmp_path, monkeypatch):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = FastAPI()
    app.include_router(create_message_router(
        resolve_identity=_identity,
        project_root=str(tmp_path),
        store=store,
    ))
    client = TestClient(app)

    submitted = client.post("/api/messages", json={
        "subject": "Maths question",
        "message": "Can you explain fractions?",
        "category": "homework",
    })
    assert submitted.status_code == 200
    message_id = submitted.json()["message"]["id"]

    inbox = client.get("/api/admin/messages")
    assert inbox.status_code == 200
    assert inbox.json()["messages"][0]["id"] == message_id

    monkeypatch.setattr(
        "src.webapp.message_routes.send_support_reply",
        lambda **_kwargs: ("sent", None),
    )
    reply = client.post(f"/api/admin/messages/{message_id}/reply", json={
        "reply": "Start by splitting the whole into equal parts.",
        "send_email": True,
    })
    assert reply.status_code == 200
    assert reply.json()["email_status"] == "sent"

    user_inbox = client.get("/api/messages")
    body = user_inbox.json()["messages"][0]
    assert body["status"] == "replied"
    assert body["replies"][0]["reply"].startswith("Start by")


def test_admin_key_is_enforced_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    app = FastAPI()
    app.include_router(create_message_router(
        resolve_identity=_identity,
        project_root=str(tmp_path),
        store=MessageStore(str(tmp_path / "messages.db")),
    ))
    client = TestClient(app)
    assert client.get("/api/admin/messages").status_code == 403
    assert client.get("/api/admin/messages", headers={"X-Admin-Key": "secret"}).status_code == 200
