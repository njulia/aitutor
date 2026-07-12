from __future__ import annotations

import pytest

from conftest import register_or_login

pytestmark = pytest.mark.api


def test_register_cookie_is_http_only_and_not_email_bearing(client, unique_email) -> None:
    response = client.post(
        "/api/register",
        json={"email": unique_email, "password": "StrongPass123!"},
    )
    assert response.status_code == 200, response.text
    cookie = response.headers.get("set-cookie", "")
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()
    assert unique_email not in cookie


def test_logout_revokes_the_server_session(client, unique_email) -> None:
    register_or_login(client, unique_email)
    assert client.get("/api/account").status_code == 200
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/account").status_code == 401


def test_admin_dashboard_rejects_anonymous_and_normal_parent(client, unique_email) -> None:
    assert client.get("/admin").status_code == 403
    register_or_login(client, unique_email)
    assert client.get("/admin").status_code == 403


def test_admin_allowlisted_parent_can_open_dashboard(admin_client) -> None:
    response = admin_client.get("/admin")
    assert response.status_code == 200
    status = admin_client.get("/api/admin/access-status")
    assert status.status_code == 200
    assert status.json()["is_admin"] is True


def test_parent_can_enable_export_and_clear_structured_memory(authenticated_client) -> None:
    students = authenticated_client.get("/api/students")
    assert students.status_code == 200, students.text
    student_id = students.json()["students"][0]["id"]

    initial = authenticated_client.get(f"/api/memory/{student_id}")
    assert initial.status_code == 200
    assert initial.json()["memory"]["settings"]["enabled"] is False

    enabled = authenticated_client.put(
        f"/api/memory/{student_id}/settings",
        json={"enabled": True, "retention_days": 90},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["settings"]["enabled"] is True

    exported = authenticated_client.get(f"/api/memory/{student_id}/export")
    assert exported.status_code == 200
    payload = exported.json()["memory_export"]
    assert payload["settings"]["enabled"] is True
    assert "exported_at" in payload
    assert "raw conversations are not stored" in payload["notice"].lower()
    assert "email" not in str(payload).lower()

    cleared = authenticated_client.delete(
        f"/api/memory/{student_id}?include_preferences=true"
    )
    assert cleared.status_code == 200
