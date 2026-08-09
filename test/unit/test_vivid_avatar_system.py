from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_character_customiser_uses_shared_vivid_renderer_and_age_context() -> None:
    page = (ROOT / "static/character-customise.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/character-customise.js").read_text(encoding="utf-8")
    style = (ROOT / "static/css/character-customise.css").read_text(encoding="utf-8")

    assert page.index("avatar-character.js") < page.index("character-customise.js")
    assert "data-character-action=\"wave\"" not in page
    assert "data-character-action=\"dance\"" in page
    assert "data-character-action=\"celebrate\"" in page
    assert "Tap my character to cheer" in page
    assert "id=\"character-age-badge\"" in page
    assert "grows with your age" in page
    assert "Trousers or dress" in page
    assert 'data-choices="bottoms"' in page
    assert "window.HomeworkMagicAvatar" in script
    assert "Avatar.hydrateFigure" in script
    assert "Avatar.enableTilt" in script
    assert "Avatar.play(previewFigure" in script
    assert "data.learner" in script
    assert "lifetime_xp" in script
    assert "innerHTML" not in script
    assert "localStorage" not in script
    assert "camera" not in script.lower()
    assert "geolocation" not in script.lower()
    assert ".hm-char-character-stage" in style
    assert "perspective: 750px" in style
    assert "min-height: 44px" in style
    assert "@media (prefers-reduced-motion: reduce)" in style


def test_avatar_renderer_has_bounded_age_growth_and_rich_safe_choices() -> None:
    renderer = (ROOT / "static/js/avatar-character.js").read_text(encoding="utf-8")

    assert "Math.max(5, Math.min(11" in renderer
    for age in range(5, 12):
        assert f"{age}:" in renderer
    assert "age.scale * (XP_SCALES[growth.stage] || 1)" in renderer
    assert "Math.max(0.78, Math.min(1.13" in renderer
    assert "pink_dress" in renderer
    assert "star_jacket" in renderer
    assert "sunshine_dungarees" in renderer
    assert "rainbow_high_tops" in renderer
    assert "addRainbowGradient" in renderer
    assert "hm-avatar3d-rainbow-shoe-base" in renderer
    assert "navy_trousers" in renderer
    assert "blue_jeans" in renderer
    assert "purple_trousers" in renderer
    assert "purple_dress" in renderer
    assert "space_buns" not in renderer
    assert "curly" not in renderer.lower()
    assert "purple" in renderer
    assert "teal" in renderer
    assert "feDropShadow" in renderer
    assert "hm-avatar3d-face-highlight" in renderer
    assert "hm-avatar3d-sleeve-short" in renderer
    assert "hm-avatar3d-tshirt-forearm" in renderer
    assert "setAttribute('stop-color'" in renderer
    assert "['dance', 'celebrate']" in renderer
    assert "wave" not in renderer.lower()
    assert "prefersReducedMotion" in renderer
    assert "fetch(" not in renderer
    assert "localStorage" not in renderer
    assert "innerHTML" not in renderer


def test_boy_face_and_blue_tshirt_have_requested_polish() -> None:
    renderer = (ROOT / "static/js/avatar-character.js").read_text(encoding="utf-8")
    stylesheet = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")
    navigation = (ROOT / "static/js/auth-nav.js").read_text(encoding="utf-8")

    assert (
        '.hm-character-avatar[data-character="boy"] .hm-avatar3d-face-highlight '
        "{ display: none; }"
    ) in stylesheet
    assert "applyEyeGeometry(figure, safeProfile)" in renderer
    assert "const whiteWidth = isGirl ? '10.5' : '13'" in renderer
    assert (
        '.hm-character-avatar[data-clothes="blue_tshirt"] '
        ".hm-avatar3d-sleeve-long { display: none; }"
    ) in stylesheet
    assert (
        '.hm-character-avatar[data-clothes="blue_tshirt"] '
        ".hm-avatar3d-sleeve-short"
    ) in stylesheet
    assert "hm-avatar3d-tshirt-forearm" in renderer
    assert "Wave" not in navigation
    assert "wave" not in navigation.lower()


def test_spiky_hair_covers_the_full_top_of_the_head() -> None:
    renderer = (ROOT / "static/js/avatar-character.js").read_text(encoding="utf-8")

    assert "hm-avatar3d-hair-spiky-cap" in renderer
    assert "M40 85 C39 64 47 49 61 43" in renderer
    assert "C133 49 141 64 140 85" in renderer
    assert "M40 83 L43 56" in renderer
    assert "L143 51 L140 84" in renderer


def test_dresses_keep_their_named_colour_and_girl_eyes_are_gentler() -> None:
    renderer = (ROOT / "static/js/avatar-character.js").read_text(encoding="utf-8")
    stylesheet = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")

    assert "pink_dress: ['#ffb8d2', '#f24f94', '#b72164']" in renderer
    assert "purple_dress: ['#d6b6ff', '#8b5cf6', '#5631a5']" in renderer
    assert "stop.style.setProperty('stop-color', colours[index])" in renderer
    assert "const whiteWidth = isGirl ? '10.5' : '13'" in renderer
    assert "iris.setAttribute('r', isGirl ? '5.2' : '7')" in renderer
    assert "pupil.setAttribute('r', isGirl ? '2.6' : '3.5')" in renderer
    assert "hm-avatar3d-girl-eyelid" in renderer
    assert "hm-avatar3d-girl-eyelashes" in renderer
    assert (
        '.hm-character-avatar[data-character="girl"] '
        ".hm-avatar3d-girl-eyelashes { display: inline; }"
    ) in stylesheet


def test_girl_has_a_smaller_head_and_slimmer_character_proportions() -> None:
    renderer = (ROOT / "static/js/avatar-character.js").read_text(encoding="utf-8")

    assert "const GIRL_PROPORTION_TRANSFORMS" in renderer
    assert "head: 'matrix(0.86 0 0 0.86 12.6 13.44)'" in renderer
    assert "torso: 'matrix(0.8 0 0 1 18 0)'" in renderer
    assert "lower: 'matrix(0.88 0 0 1 10.8 0)'" in renderer
    assert "armLeft: 'translate(6 0)'" in renderer
    assert "armRight: 'translate(-6 0)'" in renderer
    assert renderer.count("hm-avatar3d-proportions-head") >= 3
    assert "hm-avatar3d-proportions-torso" in renderer
    assert "hm-avatar3d-proportions-lower" in renderer
    assert "profile.character === 'girl'" in renderer
    assert "else group.removeAttribute('transform')" in renderer
    assert "applyCharacterProportions(figure, safeProfile)" in renderer


def test_avatar_api_returns_only_minimised_age_context() -> None:
    routes = (ROOT / "src/webapp/reward_routes.py").read_text(encoding="utf-8")
    store = (ROOT / "src/webapp/reward_store.py").read_text(encoding="utf-8")

    assert "def _avatar_age_context" in routes
    assert 'return {"age": age, "year_group": year_group}' in routes
    assert '"learner": _avatar_age_context(learner)' in routes
    assert "date_of_birth" not in routes
    assert '"star_jacket": "Star jacket"' in store
    assert '"sunshine_dungarees": "Sunshine dungarees"' in store
    assert '"rainbow_high_tops": "Rainbow high-tops"' in store
    assert '"ponytail": "Ponytail"' in store
    assert '"navy_trousers": "Navy trousers"' in store
    assert '"purple_dress": "Purple dress"' in store
    assert "character_bottom_profiles" in store
    assert '"curly": "Curly"' not in store
    assert '"space_buns": "Space buns"' not in store
    assert '"purple": "Purple"' in store
    assert '"teal": "Teal"' in store
