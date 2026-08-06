"""Contracts for the parent-facing billing status used by the plans page."""
from __future__ import annotations

import pytest


pytestmark = pytest.mark.api


def test_billing_status_requires_a_parent_account(client) -> None:
    response = client.get("/api/billing/status")

    assert response.status_code == 401


def test_billing_status_is_private_and_reports_no_active_plan(authenticated_client) -> None:
    response = authenticated_client.get("/api/billing/status")

    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    data = response.json()
    assert data["success"] is True
    assert data["has_subscription"] is False
    assert data["subscription"] is None
    assert data["management"] == {
        "can_change": False,
        "can_cancel": False,
        "can_manage": False,
        "can_purchase": True,
        "is_beta": False,
    }
    assert data["refresh"] == {"attempted": False, "succeeded": True}
    assert set(data["plan_availability"]) == {
        "trial_5day",
        "homework_monthly",
        "elevenplus_monthly",
    }
