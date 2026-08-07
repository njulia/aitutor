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
                        "character": "girl",
                        "clothes": "pink_dress",
                        "shoes": "trainers",
                        "skin_tone": "warm",
                        "hair_colour": "red",
                        "hair_length": "long",
                        "hair_style": "ponytail",
                        "eye_shape": "round",
                        "eye_colour": "green",
                        "nose": "button",
                        "mouth": "smile",
                        "eyebrows": "soft",
                        "customised": True,
                    },
                    "growth": {
                        "stage": 4,
                        "name": "Clever Champion",
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
                "message": "Your character style is saved!",
                "avatar": {
                    "profile": {
                        "character": "boy",
                        "clothes": "blue_tshirt",
                        "shoes": "boots",
                        "skin_tone": "tan",
                        "hair_colour": "black",
                        "hair_length": "short",
                        "hair_style": "spiky",
                        "eye_shape": "almond",
                        "eye_colour": "blue",
                        "nose": "small",
                        "mouth": "grin",
                        "eyebrows": "arched",
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
    expect(page.locator("[data-avatar-growth-name]")).to_have_text("Clever Champion")
    expect(page.locator("[data-avatar-growth-xp]")).to_have_text("640 XP")
    page.get_by_role("button", name="🎨 Customise my character").click()
    page.get_by_role("button", name="Boy character").click()
    page.get_by_role("button", name="Black hair").click()
    page.get_by_label("Hair length").select_option("short")
    page.get_by_label("Hair style").select_option("spiky")
    page.get_by_text("👕 Clothes & shoes", exact=True).click()
    page.get_by_role("button", name="Blue T-shirt").click()
    page.get_by_role("button", name="Adventure boots").click()
    page.get_by_role("button", name="Save my character").click()
    expect(page.locator("[data-avatar-customise-status]")).to_have_text(
        "Your character style is saved!"
    )
    expect(page.locator(".hm-character-avatar-preview")).to_have_attribute(
        "data-character", "boy"
    )
    expect(page.locator(".hm-character-avatar-preview")).to_have_attribute(
        "data-clothes", "blue_tshirt"
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
