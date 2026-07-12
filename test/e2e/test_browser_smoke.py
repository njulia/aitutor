from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e
BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


@pytest.fixture(autouse=True)
def require_e2e_enabled():
    if os.getenv("RUN_E2E", "0").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_E2E=1 and start the website to run browser tests")


def test_homepage_and_app_load(page: Page) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    expect(page).to_have_title(re.compile("Homework"))
    expect(page.get_by_text("Homework Magic").first).to_be_visible()

    page.goto(f"{BASE_URL}/app", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("Generate Homework")


def test_no_public_script_cdn_on_learner_pages(page: Page) -> None:
    requested_hosts: set[str] = set()

    def record_request(request):
        if request.resource_type == "script":
            requested_hosts.add(request.url.split("/", 3)[2])

    page.on("request", record_request)
    page.goto(f"{BASE_URL}/app", wait_until="networkidle")
    assert requested_hosts <= {BASE_URL.split("//", 1)[1]}
