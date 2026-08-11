from __future__ import annotations


def test_capybara_playtime_page_and_api_are_daily_goal_gated(
    authenticated_client, monkeypatch
):
    account = authenticated_client.get("/api/account").json()
    student = account["students"][0]

    page = authenticated_client.get("/playtime")
    assert page.status_code == 200
    assert "Capybara Playtime" in page.text
    assert "/static/js/playtime.js" in page.text

    monkeypatch.setattr(
        "src.webapp.reward_routes.get_daily_goal_stats",
        lambda student_id, daily_goal: {
            "daily_goal": daily_goal,
            "daily_counts": [{"date": "2026-08-11", "count": 0}],
        },
    )
    locked = authenticated_client.post(
        "/api/rewards/capybara/activity",
        json={"student_id": student["id"], "activity": "play"},
    )
    assert locked.status_code == 403
    assert "Daily Goal" in locked.json()["detail"]


def test_capybara_fruit_and_play_never_change_reward_wallet(
    authenticated_client, monkeypatch
):
    account = authenticated_client.get("/api/account").json()
    student = account["students"][0]
    monkeypatch.setattr(
        "src.webapp.reward_routes.get_daily_goal_stats",
        lambda student_id, daily_goal: {
            "daily_goal": daily_goal,
            "daily_counts": [{"date": "2026-08-11", "count": daily_goal}],
        },
    )
    before = authenticated_client.get("/api/rewards").json()
    fruit = authenticated_client.put(
        "/api/rewards/capybara/fruit",
        json={"student_id": student["id"], "fruit": "watermelon"},
    )
    assert fruit.status_code == 200
    play = authenticated_client.post(
        "/api/rewards/capybara/activity",
        json={"student_id": student["id"], "activity": "play"},
    )
    assert play.status_code == 200
    assert play.json()["pet"]["no_xp_change"] is True
    assert play.json()["pet"]["no_gift_points_change"] is True
    after = authenticated_client.get("/api/rewards").json()
    assert after["wallet"]["lifetime_xp"] == before["wallet"]["lifetime_xp"]
    assert after["wallet"]["gift_points"] == before["wallet"]["gift_points"]


def test_capybara_playtime_has_body_and_real_activity_visuals(authenticated_client):
    page = authenticated_client.get('/playtime')
    assert page.status_code == 200
    assert 'hm-capy-body' in page.text
    assert 'hm-prop-ball' in page.text
    assert 'hm-prop-food' in page.text
    assert 'hm-prop-poo' in page.text
    assert 'hm-prop-broom' in page.text
    assert 'hm-sleep-z' in page.text
    assert 'Jump &amp; roll!' in page.text
    assert 'Watch me eat!' in page.text
    assert 'Find &amp; sweep!' in page.text
    assert 'Close eyes &amp; snooze' in page.text
