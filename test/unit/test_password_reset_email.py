from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.webapp import email_service
from src.webapp.email_service import password_reset_email_configuration_issues

pytestmark = pytest.mark.unit


def _clear_email_environment(monkeypatch) -> None:
    for name in (
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_USE_SSL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_password_reset_email_requires_host_and_sender(monkeypatch) -> None:
    _clear_email_environment(monkeypatch)

    issues = password_reset_email_configuration_issues()

    assert "SMTP_HOST must be configured for password reset email" in issues
    assert "SMTP_FROM must be configured for password reset email" in issues


def test_password_reset_email_accepts_authenticated_starttls(monkeypatch) -> None:
    _clear_email_environment(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "support@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("SMTP_FROM", "Homework Magic <support@example.com>")

    assert password_reset_email_configuration_issues() == []


def test_password_reset_email_rejects_invalid_port(monkeypatch) -> None:
    _clear_email_environment(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "support@example.com")
    monkeypatch.setenv("SMTP_PORT", "not-a-port")

    assert "SMTP_PORT must be a valid TCP port" in password_reset_email_configuration_issues()


class _FakeSMTP:
    messages = []

    def __init__(self, host, port, timeout):
        assert host == "smtp.example.com"
        assert port == 587
        assert timeout == 15

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def ehlo(self):
        return None

    def starttls(self, context):
        assert context is not None

    def login(self, username, password):
        assert username == "smtp-user"
        assert password == "smtp-password"

    def send_message(self, message):
        self.messages.append(message)


def _configure_fake_smtp(monkeypatch) -> None:
    _FakeSMTP.messages = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_FROM", "Homework Magic <hello@example.com>")
    monkeypatch.setenv("APP_BASE_URL", "https://homework.example")
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSMTP)


def test_registration_confirmation_has_plain_html_and_privacy_guidance(monkeypatch) -> None:
    _configure_fake_smtp(monkeypatch)

    status, error = email_service.send_registration_confirmation_email(
        to_email="parent@example.com"
    )

    assert (status, error) == ("sent", None)
    message = _FakeSMTP.messages[0]
    assert message["To"] == "parent@example.com"
    assert message["Subject"] == "Welcome to Homework Magic"
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "parent or guardian account has been created successfully" in plain
    assert "https://homework.example/app" in plain
    assert "child’s full name" in plain
    assert "Start using Homework Magic" in html


def test_subscription_confirmation_names_plan_and_access_period(monkeypatch) -> None:
    _configure_fake_smtp(monkeypatch)

    status, error = email_service.send_subscription_confirmation_email(
        to_email="parent@example.com",
        plan="elevenplus_monthly",
        current_period_end=datetime(2026, 8, 20, tzinfo=UTC),
    )

    assert (status, error) == ("sent", None)
    message = _FakeSMTP.messages[0]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert message["Subject"] == "Your Homework Magic subscription is active"
    assert "11+ Premium access is now active" in plain
    assert "20 August 2026" in plain
    assert "payment-card information" in plain
