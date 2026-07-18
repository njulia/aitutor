"""Shared fixtures for live browser end-to-end tests.

The suite is opt-in because it needs a running web server and a Playwright
browser. AI and payment endpoints are mocked in browser tests so no provider
keys or paid calls are required.
"""
from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import Page, Route


def _enabled() -> bool:
    return os.getenv("RUN_E2E", "0").strip().lower() in {"1", "true", "yes"}


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    if not _enabled():
        pytest.skip("Set RUN_E2E=1 and start the website to run browser tests")

    base_url = (
        os.getenv("E2E_BASE_URL")
        or os.getenv("BASE_URL")
        or "http://127.0.0.1:5000"
    ).rstrip("/")
    try:
        with urlopen(f"{base_url}/api/health", timeout=5) as response:
            if response.status != 200:
                pytest.fail(f"E2E server health check returned HTTP {response.status}")
    except URLError as exc:
        pytest.fail(
            f"E2E server is not reachable at {base_url}. Start it before running tests: {exc}"
        )
    return base_url


@pytest.fixture(autouse=True)
def require_live_server(e2e_base_url: str) -> None:
    """Make every test in this directory opt-in and health checked."""


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict:
    """Use a system Chromium when Playwright's managed browser is unavailable."""
    executable = os.getenv("E2E_BROWSER_EXECUTABLE")
    args: dict = {"headless": True}
    if executable:
        args["executable_path"] = executable
    return args


@pytest.fixture
def fulfil_json():
    def _fulfil(route: Route, body: dict, status: int = 200) -> None:
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(body),
        )

    return _fulfil


@pytest.fixture
def mock_common_app_endpoints(page: Page, fulfil_json) -> None:
    page.route(
        "**/api/subjects",
        lambda route: fulfil_json(
            route,
            {
                "primary": ["Maths", "English", "Science"],
                "eleven_plus": [
                    "Maths",
                    "English",
                    "Verbal Reasoning",
                    "Non-Verbal Reasoning",
                ],
                "eleven_plus_year_round": [
                    "Maths-1year",
                    "English-1year",
                    "VerbalReasoning-1year",
                    "NonVerbalReasoning-1year",
                ],
            },
        ),
    )
    page.route(
        "**/api/client-id",
        lambda route: fulfil_json(route, {"client_id": "anon_e2e_safe_id"}),
    )
    page.route(
        "**/api/check-subscription*",
        lambda route: fulfil_json(
            route,
            {"has_subscription": False, "logged_in": False, "student_id": "anon_e2e_safe_id"},
        ),
    )
