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
    assert "Save my character" in script
    assert "'/api/rewards/avatar'" in script
    assert "homeworkmagic:xp-updated" in script
    assert "Little Learner" in script
    assert "Learning Legend" in script
    assert "createCharacterFigure" in script
    assert "CHARACTER_PRESETS" in script
    assert "Girl character" in script
    assert "Boy character" in script
    assert "hm-character-cheek" in script
    assert "hm-character-face-detail" in script
    for field in (
        "character",
        "clothes",
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
        assert f"{field}:" in script
    assert "capybara" not in script.lower()
    assert "activeRole === 'kid' ? '/api/kid-logout' : '/api/logout'" in script
    assert "innerHTML" not in script


def test_kid_avatar_uses_css_character_layers_and_touch_sized_styles() -> None:
    stylesheet = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")

    assert ".hm-character-avatar" in stylesheet
    assert '.hm-character-avatar[data-character="girl"]' in stylesheet
    assert '.hm-character-avatar[data-character="boy"]' in stylesheet
    assert '.hm-character-avatar[data-character="girl"] .hm-character-face-detail' in stylesheet
    assert '.hm-character-avatar[data-character="boy"] .hm-character-face-detail' in stylesheet
    assert '.hm-character-avatar[data-character="boy"] .hm-character-cheek' in stylesheet
    assert '.hm-character-avatar[data-hair-style="ponytail"]' in stylesheet
    assert '.hm-character-avatar[data-hair-style="curly"]' in stylesheet
    assert '.hm-character-avatar[data-eye-shape="almond"]' in stylesheet
    assert '.hm-character-avatar[data-mouth="grin"]' in stylesheet
    assert '.hm-character-avatar[data-clothes="pink_dress"]' in stylesheet
    assert '.hm-character-avatar[data-shoes="boots"]' in stylesheet
    assert ".hm-kid-avatar-button" in stylesheet
    assert "width: 56px;" in stylesheet
    assert ".hm-kid-avatar-menu[hidden]" in stylesheet
    assert ".hm-kid-avatar-action" in stylesheet
    assert '.hm-kid-avatar[data-growth-stage="6"]' in stylesheet
    assert ".hm-kid-avatar-growth-progress" in stylesheet
    assert ".hm-kid-avatar-customiser" in stylesheet
    assert ".hm-kid-avatar-editor-preview" in stylesheet
    assert ".hm-kid-avatar-editor-section" in stylesheet
    assert ".hm-kid-avatar-select-field" in stylesheet
    assert ".hm-kid-avatar-choice.is-selected" in stylesheet
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet
    assert ".hm-kid-avatar { display: none !important; }" in stylesheet


@pytest.mark.parametrize("relative_path", ROLE_AWARE_PAGES)
def test_role_aware_pages_load_fresh_avatar_assets(relative_path: str) -> None:
    page = (ROOT / "static" / relative_path).read_text(encoding="utf-8")

    assert "/static/css/theme.css?v=20260807-cute-character-avatar-review-stable" in page
    assert "/static/js/auth-nav.js?v=20260807-cute-character-avatar-review-stable" in page


def test_learning_app_reuses_shared_session_request_for_avatar() -> None:
    page = (ROOT / "static/app.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    assert page.index("session-context.js") < page.index("auth-nav.js")
    assert page.index("auth-nav.js") < page.index("app.js?v=")
    assert "HomeworkMagicSession.get(false)" in script
    assert "authenticated && currentSessionRole !== 'kid'" in script
    assert "kid-avatar" in page.split("app.js?v=", 1)[1].split('"', 1)[0]
