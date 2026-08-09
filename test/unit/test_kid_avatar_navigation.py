from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]

ROLE_AWARE_PAGES = (
    "app.html",
    "beta-feedback.html",
    "beta.html",
    "calm-eleven-plus-practice.html",
    "check-my-homework.html",
    "elevenplus-mock-exams.html",
    "elevenplus-practice.html",
    "elevenplus-topic-mastery.html",
    "elevenplus-year-round-plan.html",
    "elevenplus/articles.html",
    "index.html",
    "ks1-homework.html",
    "ks2-homework.html",
    "memory.html",
    "messages.html",
    "pricing.html",
    "privacy.html",
    "progress.html",
    "refund-policy.html",
    "rewards.html",
    "safety.html",
    "terms.html",
    "year-3-english-reading-practice.html",
    "year-3-maths-practice.html",
) + tuple(
    str(path.relative_to(ROOT / "static"))
    for path in sorted((ROOT / "static/elevenplus").glob("*.html"))
    if path.name != "articles.html"
)


def test_kid_avatar_is_role_safe_personalised_and_useful() -> None:
    script = (ROOT / "static/js/auth-nav.js").read_text(encoding="utf-8")
    renderer = (ROOT / "static/js/avatar-character.js").read_text(encoding="utf-8")

    assert "context.role === 'kid'" in script
    assert "context.student || {}" in script
    assert "data-kid-avatar-button" in script
    assert "aria-expanded" in script
    assert "event.key === 'Escape'" in script
    assert "Open ${firstName}'s learning menu" in script
    assert "Year ${year} explorer" in script
    assert "'/app', '🚀', 'Start a quest'" in script
    assert "'/progress', '📈', 'My progress'" in script
    assert "'/rewards', '🎁', 'My rewards'" in script
    assert "Customise my character" in script
    assert "homeworkmagic:xp-updated" in script
    assert "Little Learner" in script
    assert "HomeworkMagicAvatar" in script
    assert "Avatar.createFigure" in script
    assert "Avatar.applyAll" in script
    assert "data-avatar-reaction" in script
    assert "createReaction('wave'" not in script
    assert "createReaction('dance'" in script
    assert "createReaction('celebrate'" in script
    assert "Age ${age.age} look" in script
    assert "CHARACTER_PRESETS" in renderer
    assert "Girl character" in renderer
    assert "Boy character" in renderer
    assert "hm-avatar3d-cheek" in renderer
    assert "feDropShadow" in renderer
    assert "linearGradient" in renderer
    assert "ageDetails" in renderer
    assert "AGE_SCALES" in renderer
    assert "enableTilt" in renderer
    assert "prefers-reduced-motion: reduce" in renderer
    for field in (
        "character",
        "clothes",
        "bottoms",
        "shoes",
        "skin_tone",
        "hair_colour",
        "hair_length",
        "hair_style",
        "eye_shape",
        "eye_colour",
        "nose",
        "mouth",
        "eyebrows",
    ):
        assert f"{field}:" in renderer
    assert "capybara" not in script.lower()
    assert "activeRole === 'kid' ? '/api/kid-logout' : '/api/logout'" in script
    assert "innerHTML" not in script
    assert "innerHTML" not in renderer


def test_kid_avatar_uses_css_character_layers_and_touch_sized_styles() -> None:
    stylesheet = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")

    assert ".hm-character-avatar" in stylesheet
    assert '.hm-character-avatar[data-avatar-renderer="vivid-3d"]' in stylesheet
    assert '.hm-character-avatar[data-character="boy"] .hm-avatar3d-face-boy' in stylesheet
    assert '.hm-character-avatar[data-hair-style="ponytail"] .hm-avatar3d-ponytail' in stylesheet
    assert 'data-hair-style="curly"' not in stylesheet
    assert 'data-hair-style="space_buns"' not in stylesheet
    assert "const whiteWidth = isGirl ? '10.5' : '13'" in (
        ROOT / "static/js/avatar-character.js"
    ).read_text(encoding="utf-8")
    assert '.hm-character-avatar[data-mouth="grin"] .hm-avatar3d-mouth-grin' in stylesheet
    assert '.hm-character-avatar[data-bottoms="pink_dress"] .hm-avatar3d-dress-skirt' in stylesheet
    assert '.hm-character-avatar[data-shoes="rainbow_high_tops"]' in stylesheet
    assert ".hm-avatar3d-rainbow-shoe-base" in stylesheet
    assert '.hm-character-avatar[data-age-stage="1"] .hm-avatar3d-head-group' in stylesheet
    assert '.hm-character-avatar[data-age-stage="4"] .hm-avatar3d-head-group' in stylesheet
    assert "hm-avatar3d-wave" not in stylesheet
    assert "hm-avatar3d-dance" in stylesheet
    assert "hm-avatar3d-pop" in stylesheet
    assert ".hm-kid-avatar-button" in stylesheet
    assert "width: 56px;" in stylesheet
    assert ".hm-kid-avatar-menu[hidden]" in stylesheet
    assert ".hm-kid-avatar-action" in stylesheet
    assert '.hm-character-avatar[data-growth-stage="6"] .hm-avatar3d-sparkle' in stylesheet
    assert ".hm-kid-avatar-growth-progress" in stylesheet
    assert ".hm-kid-avatar-reactions" in stylesheet
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet
    assert ".hm-kid-avatar { display: none !important; }" in stylesheet


@pytest.mark.parametrize("relative_path", ROLE_AWARE_PAGES)
def test_role_aware_pages_load_fresh_avatar_assets(relative_path: str) -> None:
    page = (ROOT / "static" / relative_path).read_text(encoding="utf-8")

    theme = "/static/css/theme.css?v=20260809-avatar-eyes-dresses-1"
    renderer = "/static/js/avatar-character.js?v=20260809-avatar-eyes-dresses-1"
    navigation = "/static/js/auth-nav.js?v=20260809-avatar-polish-1"
    assert theme in page
    assert renderer in page
    assert navigation in page
    assert page.index(renderer) < page.index(navigation)


def test_learning_app_reuses_shared_session_request_for_avatar() -> None:
    page = (ROOT / "static/app.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    assert page.index("session-context.js") < page.index("avatar-character.js")
    assert page.index("avatar-character.js") < page.index("auth-nav.js")
    assert page.index("auth-nav.js") < page.index("app.js?v=")
    assert "HomeworkMagicSession.get(false)" in script
    assert "authenticated && currentSessionRole !== 'kid'" in script
    assert "kid-avatar" in page.split("app.js?v=", 1)[1].split('"', 1)[0]
