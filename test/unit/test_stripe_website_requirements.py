"""Public website disclosures required for a clear Stripe purchasing journey."""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"


def _page(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_pricing_discloses_currency_renewal_delivery_and_policies() -> None:
    pricing = _page("pricing.html")

    assert "pounds sterling (GBP)" in pricing
    assert "£4.99 GBP is charged each month until cancelled" in pricing
    assert "£9.99 GBP is charged each month until cancelled" in pricing
    assert "does not renew automatically" in pricing
    assert "There is nothing to ship" in pricing
    assert 'href="/terms"' in pricing
    assert 'href="/refund-policy"' in pricing
    assert "contact@homeworkmagic.co.uk" in pricing


def test_homepage_and_contact_page_expose_direct_support_and_legal_links() -> None:
    homepage = _page("index.html")
    contact = _page("messages.html")

    assert "mailto:contact@homeworkmagic.co.uk" in homepage
    assert 'href="/terms"' in homepage
    assert 'href="/refund-policy"' in homepage
    assert "mailto:contact@homeworkmagic.co.uk" in contact
    assert 'id="contact-form"' in contact


@pytest.mark.parametrize("route", ["/terms", "/refund-policy", "/privacy"])
def test_legal_routes_render_configured_operator_details(client, monkeypatch, route) -> None:
    monkeypatch.setenv("DATA_CONTROLLER_NAME", "Example Operator & Co")
    monkeypatch.setenv("PRIVACY_CONTACT_EMAIL", "privacy@example.com")
    monkeypatch.setenv("BUSINESS_CONTACT_EMAIL", "support@example.com")
    monkeypatch.setenv("PRIVACY_POSTAL_ADDRESS", "1 Example Road, London")

    response = client.get(route)

    assert response.status_code == 200
    assert "{{" not in response.text
    assert "Example Operator &amp; Co" in response.text
    assert "1 Example Road, London" in response.text


def test_refund_policy_has_clear_conditions_and_request_method() -> None:
    policy = _page("refund-policy.html")

    assert "charged more than once" in policy
    assert "payment was taken after a cancellation" in policy
    assert "within 14 days of a first purchase" in policy
    assert "original payment method" in policy
    assert "{{BUSINESS_CONTACT_EMAIL}}" in policy
