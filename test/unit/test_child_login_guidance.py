from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_child_login_page_explains_the_separate_child_code() -> None:
    page = (ROOT / "static/kid_login.html").read_text(encoding="utf-8")
    parent_login = (ROOT / "static/login.html").read_text(encoding="utf-8")

    assert "Your Child login code" in page
    assert "Find the Child login code in the Parent Dashboard" in page
    assert "different from your email and parent password" in page
    assert "PENDING_KID_LOGIN_CODE_KEY" in page
    assert "sessionStorage.removeItem(PENDING_KID_LOGIN_CODE_KEY)" in page
    assert "Your Child login code is ready. Tap Start Learning!" in page
    assert "params.get('code')" not in page
    assert "Grown-up log in" in parent_login
    assert "Child sign in with your code" in parent_login
    assert "not their email or password" in parent_login


def test_parent_dashboard_makes_child_sign_in_clear_without_putting_code_in_url() -> None:
    page = (ROOT / "static/parent_dashboard.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/parent-dashboard.js").read_text(encoding="utf-8")

    assert "Help your child sign in to their own space" in page
    assert "See child login codes" in page
    assert "Open child sign-in” next to the right code" in page
    assert "Child login code:" in script
    assert "Open child sign-in" in script
    assert "sessionStorage.setItem('homeworkmagic_pending_kid_login_code', codeValue)" in script
    assert "Open child sign-in to take this code safely to the next page" in script
    assert "window.location.assign('/kid-login?next=/app')" in script
    assert "encodeURIComponent(codeValue)" not in script


def test_app_shows_a_child_sign_in_route_to_signed_in_parents_only() -> None:
    page = (ROOT / "static/app.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    theme = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")

    assert 'id="parent-child-login-guide"' in page
    assert "Find a child’s code" in page
    assert "Find code &amp; sign in" in page
    assert "parentChildLoginGuide.hidden = currentSessionRole !== 'parent'" in script
    assert ".parent-child-login-guide" in theme
