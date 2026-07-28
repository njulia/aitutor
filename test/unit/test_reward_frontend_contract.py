from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_reward_page_is_age_appropriate_and_parent_controlled() -> None:
    page = (ROOT / "static" / "rewards.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "rewards.js").read_text(encoding="utf-8")
    assert "Your quests" in page
    assert "Lifetime XP" in page
    assert "Gift Points" in page
    assert "never goes down" in page
    assert "Parent account password" in page
    assert "Homework Magic sticker pack, pen or notebook" in page
    assert "Adult recipient's name" in page
    assert "adult recipient's UK" in page
    assert "custom-reward" not in page
    assert "/api/rewards" in script
    assert "delivery_address" in script
    assert "wallet.gift_points" in script
    assert "wallet.spendable_xp" not in script
    assert "textContent" in script
    assert "https://" not in script


def test_admin_has_a_protected_gift_fulfilment_page() -> None:
    page = (ROOT / "static" / "admin-reward-orders.html").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "static" / "js" / "admin-reward-orders.js").read_text(
        encoding="utf-8"
    )
    assert "Homework Magic gift orders" in page
    assert "Adult delivery recipient" in page
    assert "/api/admin/reward-orders" in script
    assert "textContent" in script


def test_main_learning_app_links_and_celebrates_reward_quests() -> None:
    page = (ROOT / "static" / "app.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'href="/rewards"' in page
    assert "showRewardCelebration(data.reward_update)" in script
    assert "XP for your effort" in script
