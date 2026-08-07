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
                "avatar": {
                    "profile": {
                        "colour": "rose",
                        "accessory": "crown",
                        "customised": True,
                    },
                    "growth": {
                        "stage": 4,
                        "name": "Clever Capybara",
                        "lifetime_xp": 640,
                        "progress_percent": 28,
                        "xp_to_next": 360,
                    },
                },
            },
        )

    page.route("**/api/session-context", kid_session)
    page.route(
        "**/api/rewards/avatar",
        lambda route: fulfil_json(
            route,
            {
                "success": True,
                "message": "Your capybara style is saved!",
                "avatar": {
                    "profile": {
                        "colour": "teal",
                        "accessory": "apple",
                        "customised": True,
                    },
                    "growth": {"lifetime_xp": 640},
                },
            },
        ),
    )
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
    expect(page.locator("[data-avatar-growth-name]")).to_have_text("Clever Capybara")
    expect(page.locator("[data-avatar-growth-xp]")).to_have_text("640 XP")
    page.get_by_role("button", name="🎨 Customise my capybara").click()
    page.get_by_role("button", name="Forest teal").click()
    page.get_by_role("button", name="Learning apple").click()
    page.get_by_role("button", name="Save my style").click()
    expect(page.locator("[data-avatar-customise-status]")).to_have_text(
        "Your capybara style is saved!"
    )
    expect(page.locator("[data-kid-avatar]")).to_have_attribute(
        "data-avatar-accessory", "apple"
    )
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
