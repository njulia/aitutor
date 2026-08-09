from __future__ import annotations

from playwright.sync_api import Page, expect


def test_kid_avatar_grows_with_age_and_plays_safely(
    page: Page,
    e2e_base_url: str,
    fulfil_json,
    mock_common_app_endpoints,
) -> None:
    session_requests = []
    initial_avatar = {
        "profile": {
            "character": "girl",
            "clothes": "pink_dress",
            "bottoms": "pink_dress",
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
            "stage": 3,
            "name": "Growing Star",
            "lifetime_xp": 640,
            "progress_percent": 28,
            "xp_to_next": 360,
        },
    }
    saved_avatar = {
        "profile": {
            "character": "boy",
            "clothes": "star_jacket",
            "bottoms": "purple_dress",
            "shoes": "rainbow_high_tops",
            "skin_tone": "warm",
            "hair_colour": "purple",
            "hair_length": "short",
            "hair_style": "spiky",
            "eye_shape": "round",
            "eye_colour": "green",
            "nose": "button",
            "mouth": "smile",
            "eyebrows": "soft",
            "customised": True,
        },
        "growth": {"lifetime_xp": 640},
    }

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
                "avatar": initial_avatar,
            },
        )

    def avatar_endpoint(route) -> None:
        if route.request.method == "PUT":
            fulfil_json(
                route,
                {
                    "success": True,
                    "message": "Your character style is saved!",
                    "learner": {"age": 10, "year_group": 5},
                    "avatar": saved_avatar,
                },
            )
            return
        fulfil_json(
            route,
            {
                "success": True,
                "learner": {"age": 10, "year_group": 5},
                "avatar": initial_avatar,
            },
        )

    page.route("**/api/session-context", kid_session)
    page.route("**/api/rewards/avatar", avatar_endpoint)
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
    expect(page.locator("[data-avatar-growth-name]")).to_have_text("Growing Star")
    expect(page.locator("[data-avatar-growth-xp]")).to_have_text("640 XP")
    expect(page.locator("[data-avatar-age-copy]")).to_contain_text("Age 10")
    expect(page.locator(".hm-character-avatar-mini")).to_have_attribute(
        "data-age", "10"
    )
    expect(page.get_by_role("button", name="Wave with my character")).to_have_count(0)
    page.get_by_role("button", name="Dance with my character").click()
    expect(page.locator("[data-avatar-reaction-status]")).to_contain_text(
        "happy dance"
    )

    page.get_by_role("link", name="🎨 Customise my character").click()
    expect(page).to_have_url(f"{e2e_base_url}/character-customise")
    expect(page.locator("#character-age-badge")).to_contain_text("Age 10")
    expect(page.locator(".hm-character-avatar-preview")).to_have_attribute(
        "data-age", "10"
    )
    expect(page.locator(".hm-character-avatar-preview .hm-avatar3d-svg")).to_be_visible()
    expect(page.get_by_role("button", name="Wave")).to_have_count(0)
    page.get_by_role("button", name="Boy character").click()
    expect(page.locator(
        ".hm-character-avatar-preview .hm-avatar3d-face-highlight"
    )).to_be_hidden()
    expect(page.locator(
        ".hm-character-avatar-preview .hm-avatar3d-sleeve-short"
    ).first).to_be_visible()
    expect(page.locator(
        ".hm-character-avatar-preview .hm-avatar3d-tshirt-forearm"
    ).first).to_be_visible()
    expect(page.locator(
        ".hm-character-avatar-preview .hm-avatar3d-sleeve-long"
    ).first).to_be_hidden()
    page.get_by_role("button", name="Purple hair").click()
    page.get_by_label("Hair length").select_option("short")
    expect(page.get_by_label("Hair style").locator("option")).to_have_count(3)
    expect(page.get_by_label("Hair style").locator('option[value="curly"]')).to_have_count(0)
    expect(page.get_by_label("Hair style").locator('option[value="space_buns"]')).to_have_count(0)
    page.get_by_label("Hair style").select_option("spiky")
    page.get_by_text("👕 Clothes & shoes", exact=True).click()
    page.get_by_role("button", name="Star jacket").click()
    page.get_by_role("button", name="Purple dress").click()
    page.get_by_role("button", name="Rainbow high-tops").click()
    expect(page.locator(
        ".hm-character-avatar-preview .hm-avatar3d-rainbow-shoe-base"
    ).first).to_be_visible()
    page.get_by_role("button", name="Save my character").click()
    expect(page.locator("#save-status")).to_have_text(
        "Your character style is saved!"
    )
    expect(page.locator(".hm-character-avatar-preview")).to_have_attribute(
        "data-character", "boy"
    )
    expect(page.locator(".hm-character-avatar-preview")).to_have_attribute(
        "data-clothes", "star_jacket"
    )
    expect(page.locator(".hm-character-avatar-preview")).to_have_attribute(
        "data-bottoms", "purple_dress"
    )
    page.get_by_role("button", name="Dance").click()
    expect(page.locator("#character-message")).to_contain_text("happy dance")

    requests_before_app = len(session_requests)
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")
    expect(page.get_by_role(
        "button", name="Open Ava's learning menu", exact=True
    )).to_be_visible()
    expect(page.locator("#logout-link")).to_be_hidden()
    assert len(session_requests) - requests_before_app == 1
