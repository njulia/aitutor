"""Public website disclosures required for a clear Stripe purchasing journey."""
from __future__ import annotations

import html
from pathlib import Path
import re

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"


def _page(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _visible_text(source: str) -> str:
    without_comments = re.sub(r"<!--.*?-->", " ", source, flags=re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_comments)
    return " ".join(html.unescape(without_tags).split())


def test_pricing_discloses_currency_renewal_delivery_and_policies() -> None:
    pricing = _page("pricing.html")

    assert "pounds sterling (GBP)" in pricing
    assert 'id="pricing-plans"' in pricing
    assert "Loading current plans" in pricing
    assert "There is nothing to ship" in pricing
    assert 'href="/terms"' in pricing
    assert 'href="/refund-policy"' in pricing
    assert "contact@homeworkmagic.co.uk" in pricing
    assert "50% off" not in pricing
    assert "Service operator:" in pricing
    assert "Business and service address:" in pricing
    assert "Your current subscription" in pricing
    assert "Manage or cancel subscription" in pricing
    assert "/api/billing/status?refresh=true" in pricing
    assert 'id="pricing-nav-login"' in pricing
    assert 'id="pricing-nav-logout"' in pricing

    pricing_script = _page("js/pricing.js")
    assert "/api/billing/plans" in pricing_script
    assert "/api/billing/checkout" in pricing_script


def test_homepage_and_contact_page_expose_direct_support_and_legal_links() -> None:
    homepage = _page("index.html")
    contact = _page("messages.html")

    assert "mailto:contact@homeworkmagic.co.uk" in homepage
    assert 'href="/terms"' in homepage
    assert 'href="/refund-policy"' in homepage
    assert "mailto:contact@homeworkmagic.co.uk" in contact
    assert 'id="contact-form"' in contact


@pytest.mark.parametrize("route", ["/terms", "/refund-policy", "/privacy", "/pricing"])
def test_legal_routes_render_configured_operator_details(client, monkeypatch, route) -> None:
    monkeypatch.setenv("DATA_CONTROLLER_NAME", "Example Operator & Co")
    monkeypatch.setenv("PRIVACY_CONTACT_EMAIL", "privacy@example.com")
    monkeypatch.setenv("BUSINESS_CONTACT_EMAIL", "support@example.com")
    monkeypatch.setenv("PRIVACY_POSTAL_ADDRESS", "1 Example Road, London")
    monkeypatch.setenv("BUSINESS_SUPPORT_PHONE", "+44 20 7946 0999")
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "12345678")
    monkeypatch.setenv("BUSINESS_VAT_STATUS", "Not VAT registered")

    response = client.get(route)
    visible = _visible_text(response.text)

    assert response.status_code == 200
    if route == "/pricing":
        assert response.headers["cache-control"] == "no-store, private"
    assert "{{" not in response.text
    assert "Example Operator & Co" in visible
    assert "1 Example Road, London" in visible
    assert "+44 20 7946 0999" in visible
    assert "12345678" in visible
    assert "Not VAT registered" in visible


@pytest.mark.parametrize(
    "filename",
    ["terms.html", "refund-policy.html", "privacy.html", "pricing.html"],
)
def test_required_operator_details_are_not_hidden_in_html_comments(filename: str) -> None:
    comments = " ".join(re.findall(r"<!--(.*?)-->", _page(filename), flags=re.DOTALL))

    assert "{{DATA_CONTROLLER_NAME}}" not in comments
    assert "{{PRIVACY_POSTAL_ADDRESS}}" not in comments


def test_refund_policy_has_clear_conditions_and_request_method() -> None:
    policy = _page("refund-policy.html")

    assert "charged more than once" in policy
    assert "payment was taken after a cancellation" in policy
    assert "within 14 days of a first purchase" in policy
    assert "original payment method" in policy
    assert "{{BUSINESS_CONTACT_EMAIL}}" in policy
