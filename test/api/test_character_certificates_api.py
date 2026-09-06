from __future__ import annotations

from src.webapp.reward_store import get_reward_store


def test_character_avatar_uses_the_same_certificate_cards_as_rewards(
    authenticated_client,
) -> None:
    account_data = authenticated_client.get("/api/account").json()
    account = account_data["account"]
    learner = account_data["students"][0]
    store = get_reward_store()

    # Set a deterministic XP threshold directly: this checks the display
    # contract without creating unrelated activity or quest records.
    with store.engine.begin() as conn:
        store._ensure_wallet(conn, account["id"], learner["id"], lock=False)
        conn.execute(
            store.wallets.update()
            .where(store.wallets.c.account_id == account["id"])
            .where(store.wallets.c.student_id == learner["id"])
            .values(lifetime_xp=1_000)
        )

    avatar_response = authenticated_client.get("/api/rewards/avatar")
    rewards_response = authenticated_client.get("/api/rewards")
    assert avatar_response.status_code == 200, avatar_response.text
    assert rewards_response.status_code == 200, rewards_response.text

    avatar_certificates = avatar_response.json()["avatar"]["certificates"]
    reward_certificates = rewards_response.json()["certificates"]
    assert avatar_certificates == [
        {key: value for key, value in item.items() if key != "print_url"}
        for item in reward_certificates
    ]
    assert all("print_url" not in item for item in avatar_certificates)
    homework_hero = next(
        item for item in avatar_certificates if item["code"] == "homework_hero"
    )
    assert homework_hero["unlocked"] is True
    assert homework_hero["threshold"] == 1_000
    assert homework_hero["icon"] == "🦸"
