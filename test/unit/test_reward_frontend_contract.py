from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_reward_page_is_age_appropriate_and_parent_controlled() -> None:
    page = (ROOT / "static" / "rewards.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "rewards.js").read_text(encoding="utf-8")
    pricing = (ROOT / "static" / "pricing.html").read_text(encoding="utf-8")
    assert "Your quests" in page
    assert "Lifetime XP" in page
    assert "Gift Points" in page
    assert "never goes down" in page
    assert "Everyone can earn XP" in page
    assert "A grown-up manages Gift Points, gifts and plans" in page
    assert 'id="gift-access-plan-link"' not in page
    assert "free beta access do not include physical gifts" in page
    assert "Parent account password" in page
    assert "Choose a reward your grown-up has set." in page
    assert "Gift Points are used only when a grown-up says yes." in page
    # 自定义礼物请求表单已添加（孩子可以向家长请求礼物）
    assert "custom-request-form" in page
    assert "My family rewards" in page
    assert 'id="catalog-grid"' in page
    assert "/api/rewards" in script
    assert "delivery_address" in script
    assert "wallet.gift_points" in script
    assert "gift_access.eligible" in script
    assert "button.textContent = 'Ask a grown-up'" in script
    assert "A grown-up manages Gift Points, gifts and plans" in script
    assert "/static/js/rewards.js?v=20260904-family-rewards-1" in page
    assert "if (legacyPlanLink) legacyPlanLink.remove();" in script
    assert "planLink.hidden" not in script
    assert "wallet.spendable_xp" not in script
    assert "textContent" in script
    assert "https://" not in script
    assert 'href="/rewards"' in pricing


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
