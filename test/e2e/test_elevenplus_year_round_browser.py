from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e
BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


@pytest.fixture(autouse=True)
def require_e2e_enabled():
    if os.getenv("RUN_E2E", "0").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_E2E=1 and start the website to run browser tests")


def test_year_round_plan_renders_52_week_experience(page: Page) -> None:
    page.goto(f"{BASE_URL}/elevenplus-year-round-plan", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("52")
    expect(page.locator("body")).to_contain_text("Maths")
    expect(page.locator("body")).to_contain_text("English")
    # Foundations phase shows Maths and English for Week 1
    expect(page.locator(".phase-foundations")).to_be_visible()


def test_year_round_progress_uses_browser_storage_not_child_identity(page: Page) -> None:
    page.goto(f"{BASE_URL}/elevenplus-year-round-plan", wait_until="domcontentloaded")
    storage = page.evaluate("Object.fromEntries(Object.entries(localStorage))")
    serialised = str(storage).lower()
    assert "email" not in serialised
    assert "school" not in serialised
    assert "address" not in serialised
