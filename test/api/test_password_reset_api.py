from __future__ import annotations

import pytest

from test.conftest import register_or_login

pytestmark = pytest.mark.api


def _clear_email_environment(monkeypatch) -> None:
    for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(name, raising=False)


def _configure_email(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "support@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("SMTP_FROM", "Homework Magic <support@example.com>")


def test_password_reset_reports_service_unavailable_when_email_is_not_configured(
    client, monkeypatch
) -> None:
    _clear_email_environment(monkeypatch)

    response = client.post(
        "/api/password-reset/request",
        json={"email": "parent-without-account@example.com"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "detail": "Password reset email is temporarily unavailable. Please try again later or contact support.",
    }


def test_password_reset_sends_existing_account_link_without_exposing_account(
    client, unique_email, monkeypatch
) -> None:
    _configure_email(monkeypatch)
    register_or_login(client, unique_email)
    captured = {}

    def fake_send_password_reset_email(**kwargs):
        captured.update(kwargs)
        return "sent", None

    monkeypatch.setattr(
        "src.webapp.password_reset_routes.send_password_reset_email",
        fake_send_password_reset_email,
    )

    response = client.post("/api/password-reset/request", json={"email": unique_email})

    assert response.status_code == 200
    assert response.json()["message"] == (
        "If an account matches that email, a password reset link has been sent."
    )
    assert captured["to_email"] == unique_email
    assert captured["reset_url"].startswith("http://testserver/reset-password?token=")
    assert captured["expires_minutes"] > 0
