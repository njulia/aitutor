"""Multi-route integration tests for a complete family learning journey."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_parent_account_learning_and_logout_journey(client, app_module, unique_email, monkeypatch) -> None:
    registration = client.post(
        "/api/register",
        json={"email": unique_email, "password": "StrongPass123!"},
    )
    assert registration.status_code == 200, registration.text
    assert registration.json() == {"success": True}

    account = client.get("/api/account")
    assert account.status_code == 200, account.text
    account_body = account.json()
    assert account_body["success"] is True
    assert account_body["account"]["email"] == unique_email
    default_learner = account_body["students"][0]
    assert default_learner["year_group"] in range(1, 7)
    assert default_learner["age"] in range(5, 12)

    added = client.post(
        "/api/students",
        json={"name": "Sam", "year_group": 4, "age": 8},
    )
    assert added.status_code == 200, added.text
    learner = added.json()["student"]
    assert learner["name"] == "Sam"
    assert learner["year_group"] == 4

    memory = client.put(
        f"/api/memory/{learner['id']}/settings",
        json={"enabled": True, "retention_days": 90},
    )
    assert memory.status_code == 200, memory.text
    assert memory.json()["settings"]["enabled"] is True

    def fake_generate(profile, subjects, is_eleven_plus=False):
        assert subjects == ["Maths"]
        assert is_eleven_plus is False
        return [{
            "subject": "Maths",
            "content": "1. What is 6 + 3?",
            "doc_id": "family_journey_maths",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    generated = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 4,
            "subjects": ["Maths"],
            "mode": "homework",
            "profile": {},
        },
    )
    assert generated.status_code == 200, generated.text
    homework = generated.json()["homework"][0]
    assert homework["doc_id"] == "family_journey_maths"
    assert homework["from_rag"] is True

    reviewed = client.post(
        "/api/review",
        json={
            "homework": homework["content"],
            "answers": "1. 9",
            "subject": "Maths",
            "profile": {"year_group": 4, "age": 8},
            "from_rag": False,
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["success"] is True
    assert "well done" in reviewed.json()["review"].lower()

    identity = client.get("/api/client-id")
    assert identity.status_code == 200
    resolved_learner_id = identity.json()["client_id"]
    assert "@" not in resolved_learner_id

    monkeypatch.setattr(app_module, "user_has_subscription", lambda *args, **kwargs: True)
    progress = client.get(f"/api/progress/{resolved_learner_id}")
    assert progress.status_code == 200, progress.text
    assert progress.json()["summary"]["overall"]["total_sessions"] >= 1

    exported = client.get(f"/api/memory/{learner['id']}/export")
    assert exported.status_code == 200, exported.text
    export_payload = exported.json()["memory_export"]
    assert unique_email not in str(export_payload)
    assert "raw conversations are not stored" in export_payload["notice"].lower()

    logout = client.post("/api/logout")
    assert logout.status_code == 200
    assert client.get("/api/account").status_code == 401
    assert client.get("/api/students").status_code == 401


def test_family_cannot_access_another_accounts_learner(client, unique_email) -> None:
    first_email = unique_email
    second_email = f"other-{unique_email}"

    assert client.post(
        "/api/register", json={"email": first_email, "password": "StrongPass123!"}
    ).status_code == 200
    learner = client.post(
        "/api/students", json={"name": "Alex", "year_group": 3, "age": 7}
    ).json()["student"]
    client.post("/api/logout")

    assert client.post(
        "/api/register", json={"email": second_email, "password": "StrongPass123!"}
    ).status_code == 200
    assert client.get(f"/api/memory/{learner['id']}").status_code == 404
    assert client.put(
        f"/api/students/{learner['id']}", json={"name": "Changed"}
    ).status_code == 404
    assert client.delete(f"/api/students/{learner['id']}").status_code == 404
