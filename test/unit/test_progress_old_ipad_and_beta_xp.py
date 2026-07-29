from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_progress_page_parses_on_safari_12() -> None:
    page = (ROOT / "static" / "progress.html").read_text(encoding="utf-8")

    # Safari 12 stops parsing the whole script when it sees either modern
    # operator. replaceAll() parses but is not available there at runtime.
    assert "?." not in page
    assert "??" not in page
    assert ".replaceAll(" not in page
    assert "height: 360px;" in page
    assert "height: 340px;" in page


def test_learning_app_busts_old_ipad_cache_for_beta_xp_change() -> None:
    page = (ROOT / "static" / "app.html").read_text(encoding="utf-8")

    assert "app.js?v=20260728-old-ipad-fix" in page
    assert "rag-review-fallback-beta-xp" in page


def test_beta_account_earns_xp_for_each_new_generated_activity(
    authenticated_client,
    app_module,
    monkeypatch,
) -> None:
    beta_code = "unit-test-parent-beta-code-2026"
    monkeypatch.setenv("BETA_ACCESS_ENABLED", "true")
    monkeypatch.setenv("BETA_ACCESS_CODE", beta_code)
    monkeypatch.setenv("BETA_ACCESS_MAX_FAMILIES", "15")
    monkeypatch.setenv("BETA_ACCESS_DURATION_DAYS", "14")

    redeemed = authenticated_client.post(
        "/api/billing/beta/redeem",
        json={"invite_code": beta_code},
    )
    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["plan"] == "beta_year3"

    monkeypatch.setattr(
        app_module,
        "review_homework",
        lambda *args, **kwargs: {
            "success": True,
            "review": "Good effort!",
            "score": 1,
            "max_score": 1,
        },
    )
    base_review = {
        "homework": "What is 4 + 5?",
        "answers": "9",
        "subject": "Maths",
        "profile": {"year_group": 3, "age": 7},
        "quick_review": True,
        "from_rag": True,
        "homework_doc_id": "same-rag-document",
    }

    first = authenticated_client.post(
        "/api/review",
        json={**base_review, "reward_activity_id": "act_first_activity"},
    )
    assert first.status_code == 200, first.text
    first_reward = first.json()["reward_update"]
    assert first_reward["awarded_xp"] > 0
    assert first_reward["awarded_gift_points"] == 0
    assert first_reward["gift_points_eligible"] is False

    repeated = authenticated_client.post(
        "/api/review",
        json={**base_review, "reward_activity_id": "act_first_activity"},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["reward_update"]["awarded_xp"] == 0
    assert repeated.json()["reward_update"]["already_awarded"] is True

    second = authenticated_client.post(
        "/api/review",
        json={**base_review, "reward_activity_id": "act_second_activity"},
    )
    assert second.status_code == 200, second.text
    second_reward = second.json()["reward_update"]
    assert second_reward["awarded_xp"] > 0
    assert second_reward["awarded_gift_points"] == 0

    # The Gift Points scheme has a daily activity limit, but lifetime XP must
    # continue for every new checked activity. This catches the production bug
    # where beta learners stopped gaining XP after the third review.
    third = authenticated_client.post(
        "/api/review",
        json={**base_review, "reward_activity_id": "act_third_activity"},
    )
    assert third.status_code == 200, third.text
    assert third.json()["reward_update"]["awarded_xp"] > 0

    fourth = authenticated_client.post(
        "/api/review",
        json={**base_review, "reward_activity_id": "act_fourth_activity"},
    )
    assert fourth.status_code == 200, fourth.text
    fourth_reward = fourth.json()["reward_update"]
    assert fourth_reward["awarded_xp"] > 0
    assert fourth_reward["awarded_gift_points"] == 0
    assert fourth_reward["daily_gift_activity_cap_reached"] is True
    assert fourth_reward["xp_activity_cap"] is None

    dashboard = authenticated_client.get("/api/rewards")
    assert dashboard.status_code == 200, dashboard.text
    assert (
        dashboard.json()["wallet"]["lifetime_xp"]
        >= (
            first_reward["awarded_xp"]
            + second_reward["awarded_xp"]
            + third.json()["reward_update"]["awarded_xp"]
            + fourth_reward["awarded_xp"]
        )
    )
