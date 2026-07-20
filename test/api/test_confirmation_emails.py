"""Transactional confirmation email API behaviour."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_successful_registration_schedules_confirmation_email(
    client, app_module, unique_email, monkeypatch
) -> None:
    recipients = []

    def fake_confirmation_email(*, to_email):
        recipients.append(to_email)
        return "sent", None

    monkeypatch.setattr(app_module, "send_registration_confirmation_email", fake_confirmation_email)

    response = client.post(
        "/api/register",
        json={"email": unique_email, "password": "StrongPass123!"},
    )

    assert response.status_code == 200, response.text
    assert recipients == [unique_email]


def test_failed_registration_does_not_schedule_confirmation_email(
    client, app_module, monkeypatch
) -> None:
    recipients = []
    monkeypatch.setattr(
        app_module,
        "send_registration_confirmation_email",
        lambda **kwargs: recipients.append(kwargs["to_email"]),
    )

    response = client.post(
        "/api/register",
        json={"email": "not-an-email", "password": "StrongPass123!"},
    )

    assert response.status_code == 400
    assert recipients == []
