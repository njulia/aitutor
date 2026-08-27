from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize(
    ("path", "heading"),
    [
        ("/login", "Welcome back"),
        ("/register", "Create your account"),
        ("/privacy", "Privacy notice"),
        ("/safety", "Your safety matters"),
    ],
)
def test_key_pages_have_one_visible_main_heading(
    page: Page, e2e_base_url: str, path: str, heading: str
) -> None:
    page.goto(f"{e2e_base_url}{path}", wait_until="domcontentloaded")
    visible_h1 = page.locator("h1:visible")
    expect(visible_h1).to_have_count(1)
    expect(visible_h1).to_have_text(heading)


def test_authentication_inputs_have_programmatic_labels(page: Page, e2e_base_url: str) -> None:
    page.goto(f"{e2e_base_url}/login", wait_until="domcontentloaded")
    expect(page.get_by_label("Email address", exact=True)).to_be_visible()
    expect(page.get_by_label("Password", exact=True)).to_be_visible()

    page.goto(f"{e2e_base_url}/register", wait_until="domcontentloaded")
    expect(page.get_by_label("Email address", exact=True)).to_be_visible()
    expect(page.get_by_label("Password", exact=True)).to_be_visible()
    expect(page.get_by_label("Confirm password")).to_be_visible()
