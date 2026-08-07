from __future__ import annotations

from playwright.sync_api import Page, expect


def test_kid_avatar_opens_on_home_and_learning_app(
    page: Page,
    e2e_base_url: str,
    fulfil_json,
    mock_common_app_endpoints,
) -> None:
    session_requests = []

    def kid_session(route) -> None:
        session_requests.append(route.request.url)
        fulfil_json(
            route,
            {
                "authenticated": True,
                "role": "kid",
                "student": {
                    "id": "learner_e2e",
                    "name": "Ava Explorer",
                    "year_group": 5,
                    "age": 10,
                    "is_default": True,
                },
            },
        )

    page.route("**/api/session-context", kid_session)
    page.goto(e2e_base_url, wait_until="domcontentloaded")

    avatar_button = page.get_by_role(
        "button", name="Open Ava's learning menu", exact=True
    )
    expect(avatar_button).to_be_visible()
    expect(page.locator("#home-login-link")).to_be_hidden()
    expect(page.locator("#home-logout-link")).to_be_hidden()
    avatar_button.click()
    expect(page.locator("[data-kid-avatar-name]")).to_have_text("Hi, Ava!")
    expect(page.locator("[data-kid-avatar-year]")).to_have_text("Year 5 explorer")
    expect(page.get_by_role("link", name="My progress See how your learning grows")).to_be_visible()
    expect(page.get_by_role("link", name="My rewards Check XP, levels and rewards")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("[data-kid-avatar-menu]")).to_be_hidden()

    requests_before_app = len(session_requests)
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")
    expect(page.get_by_role(
        "button", name="Open Ava's learning menu", exact=True
    )).to_be_visible()
    expect(page.locator("#logout-link")).to_be_hidden()
    assert len(session_requests) - requests_before_app == 1
