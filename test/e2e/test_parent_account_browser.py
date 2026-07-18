from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_registration_sends_guardian_confirmation_and_uses_safe_next_path(
    page: Page, e2e_base_url: str, fulfil_json
) -> None:
    captured: dict = {}

    def handle_register(route) -> None:
        captured.update(route.request.post_data_json or {})
        fulfil_json(route, {"success": True})

    page.route("**/api/register", handle_register)
    page.goto(f"{e2e_base_url}/register?next=%2Fprivacy", wait_until="domcontentloaded")
    page.get_by_label("Email address", exact=True).fill("parent-e2e@example.com")
    page.get_by_label("Password", exact=True).fill("StrongPass123!")
    page.get_by_label("Confirm password").fill("StrongPass123!")
    page.locator("#guardian-confirmed").check()
    page.get_by_role("button", name="Create Account").click()

    expect(page).to_have_url(f"{e2e_base_url}/privacy", timeout=5000)
    assert captured["email"] == "parent-e2e@example.com"
    assert captured["guardian_confirmed"] is True
    assert "student" not in captured
    assert "school" not in str(captured).lower()


def test_login_blocks_external_redirects(page: Page, e2e_base_url: str, fulfil_json) -> None:
    page.route("**/api/login", lambda route: fulfil_json(route, {"success": True}))
    page.goto(
        f"{e2e_base_url}/login?next=https%3A%2F%2Fevil.example%2Fsteal",
        wait_until="domcontentloaded",
    )
    page.get_by_label("Email address", exact=True).fill("parent-e2e@example.com")
    page.get_by_label("Password", exact=True).fill("StrongPass123!")
    page.get_by_role("button", name="Log in").click()

    expect(page).to_have_url(f"{e2e_base_url}/app")
    assert "evil.example" not in page.url


def test_child_friendly_privacy_and_safety_pages(page: Page, e2e_base_url: str) -> None:
    page.goto(f"{e2e_base_url}/privacy", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="A simple explanation for children")).to_be_visible()
    expect(page.locator("main")).to_contain_text("Use a nickname")
    expect(page.locator("main")).to_contain_text("Do not share your school")

    page.goto(f"{e2e_base_url}/safety", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="Your safety matters")).to_be_visible()
    expect(page.locator("main")).to_contain_text("999")
    expect(page.locator("main")).to_contain_text("0800 1111")
    expect(page.locator("main")).to_contain_text("trusted adult")
