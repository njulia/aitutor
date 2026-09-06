from __future__ import annotations

from src.webapp.study_buddy_store import (
    get_study_buddy_settings,
    set_max_buddies_per_learner,
    set_max_emojis_per_learner,
)


def test_admin_can_change_the_global_study_buddy_limit(admin_client, client) -> None:
    original = get_study_buddy_settings()["max_buddies_per_learner"]
    original_emoji_limit = get_study_buddy_settings()["max_emojis_per_learner"]
    try:
        client.post("/api/logout")
        denied = client.put(
            "/api/admin/study-buddy-settings",
            json={"max_buddies_per_learner": 12},
        )
        admin_login = admin_client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "StrongPass123!"},
        )
        saved = admin_client.put(
            "/api/admin/study-buddy-settings",
            json={"max_buddies_per_learner": 12, "max_emojis_per_learner": 14},
        )
        current = admin_client.get("/api/admin/study-buddy-settings")

        assert denied.status_code in {401, 403}
        assert admin_login.status_code == 200
        assert saved.status_code == 200, saved.text
        assert saved.json()["settings"]["max_buddies_per_learner"] == 12
        assert saved.json()["settings"]["max_emojis_per_learner"] == 14
        assert current.status_code == 200
        assert current.json()["settings"]["max_buddies_per_learner"] == 12
        assert current.json()["settings"]["max_emojis_per_learner"] == 14
        assert get_study_buddy_settings()["max_buddies_per_learner"] == 12
        assert get_study_buddy_settings()["max_emojis_per_learner"] == 14
    finally:
        set_max_buddies_per_learner(original)
        set_max_emojis_per_learner(original_emoji_limit)
