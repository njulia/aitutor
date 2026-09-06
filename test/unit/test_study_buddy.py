from src.webapp.study_buddy_store import (
    DAILY_EMOJI_SEND_LIMIT,
    buddy_challenges,
    buddy_challenge_notifications,
    buddy_emoji_reactions,
    buddy_requests,
    challenges_for,
    challenge_completion_notifications_for,
    acknowledge_challenge_completion_notification,
    complete_challenge_for_verified_activity,
    _subject_matches,
    CHALLENGE_CATALOG,
    DAILY_CHALLENGE_SEND_LIMIT,
    DAILY_CHALLENGE_RECEIVE_LIMIT,
    EMOJI_OPTIONS,
    approve_request,
    buddies,
    create_request,
    create_challenge,
    emoji_reactions_for,
    find_students,
    init_study_buddy_db,
    is_buddy,
    remove_buddy_for_parent,
    send_emoji_reaction,
    set_max_buddies_per_learner,
)
from pathlib import Path
import re
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError


ROOT = Path(__file__).resolve().parents[2]
from src.webapp.account_store import _engine, create_student, ensure_account, get_student, students
from src.webapp.reward_store import BADGES


def test_study_buddy_schema():
    assert buddy_challenges.c.challenge_type is not None
    assert buddy_challenges.c.xp_reward is not None
    assert buddy_challenges.c.verified_activity_count is not None
    assert buddy_challenges.c.completion_source is not None
    assert buddy_requests.c.requester_parent_approved is not None
    assert buddy_requests.c.target_parent_approved is not None
    assert buddy_requests.c.pair_key is not None
    assert buddy_emoji_reactions.c.sender_student_id is not None
    assert buddy_emoji_reactions.c.recipient_student_id is not None
    assert buddy_emoji_reactions.c.expires_at is not None
    assert buddy_challenge_notifications.c.recipient_student_id is not None
    assert buddy_challenge_notifications.c.challenge_id is not None
    assert buddy_challenge_notifications.c.seen_at is not None


def test_challenge_catalog_and_limits_are_fixed():
    assert {"maths", "english", "mixed"} <= set(CHALLENGE_CATALOG)
    assert {
        "reasoning", "11plus", "verbal_reasoning", "non_verbal_reasoning",
        "eleven_plus_maths", "eleven_plus_english",
    } <= set(CHALLENGE_CATALOG)
    assert DAILY_CHALLENGE_SEND_LIMIT == 3
    assert DAILY_CHALLENGE_RECEIVE_LIMIT == 5
    assert all(item["target_count"] > 0 and item["xp"] > 0 for item in CHALLENGE_CATALOG.values())


def test_challenge_verification_matches_real_learning_subjects():
    assert _subject_matches("maths", "Maths")
    assert _subject_matches("english", "English")
    assert _subject_matches("reasoning", "11+ Verbal Reasoning")
    assert _subject_matches("reasoning", "11+ Non-Verbal Reasoning")
    assert _subject_matches("11plus", "11+ Maths")
    assert _subject_matches("eleven_plus_maths", "11+ Maths")
    assert _subject_matches("eleven_plus_english", "11+ English")
    assert not _subject_matches("eleven_plus_maths", "Maths")
    assert _subject_matches("mixed", "Science")
    assert not _subject_matches("mixed", "Anything")
    assert not _subject_matches("maths", "English")
    assert not _subject_matches("11plus", "Maths")


def test_badge_catalog_is_effort_and_buddy_focused():
    codes = {item["code"] for item in BADGES}
    assert {"first_steps", "practice_pal", "challenge_starter", "helpful_buddy"} <= codes
    assert all("chat" not in item["description"].lower() for item in BADGES)


def test_buddy_lookup_is_an_exact_code_lookup_not_a_child_directory() -> None:
    store = (ROOT / "src/webapp/study_buddy_store.py").read_text(encoding="utf-8")

    assert "students.c.buddy_code" in store
    assert "exact, indexed lookup" in store
    assert "searchable child directory" in store
    assert "MAX_BUDDIES_PER_LEARNER = 40" in store


def test_buddy_codes_are_unique_in_the_database_and_reissued_when_needed() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    account = ensure_account(f"buddy-code-unique-{suffix}@example.com")
    first = create_student(account["id"], "Alex", 3, 7)
    second = create_student(account["id"], "Alex", 4, 8)

    assert first["buddy_code"] != second["buddy_code"]
    with pytest.raises(IntegrityError):
        with _engine().begin() as conn:
            conn.execute(
                update(students)
                .where(students.c.id == second["id"])
                .values(buddy_code=first["buddy_code"])
            )

    store = (ROOT / "src/webapp/account_store.py").read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX IF NOT EXISTS ix_students_buddy_code" in store
    assert "reissue_ids" in store


def test_admin_student_table_shows_a_short_year_and_the_buddy_code() -> None:
    dashboard = (ROOT / "static/admin.html").read_text(encoding="utf-8")
    admin_api = (ROOT / "web_app.py").read_text(encoding="utf-8")

    assert 'data-sort="buddy_code"' in dashboard
    assert "<td>${u.year_group || '-'}</td>" in dashboard
    assert "<td><code>${u.buddy_code || '-'}</code></td>" in dashboard
    assert '"buddy_code": u.get("buddy_code")' in admin_api


def test_siblings_under_one_parent_account_become_buddies_straight_away() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    account = ensure_account(f"buddy-siblings-{suffix}@example.com")
    first = create_student(account["id"], "Ari", 3, 7)
    second = create_student(account["id"], "Bo", 5, 9)

    request = create_request(first["id"], second["id"])

    assert request["status"] == "active"
    assert is_buddy(first["id"], second["id"])
    assert {buddy["student_id"] for buddy in buddies(first["id"])} == {second["id"]}


def test_a_parent_can_approve_again_after_declining_a_buddy_request() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    first_account = ensure_account(f"buddy-reapprove-one-{suffix}@example.com")
    second_account = ensure_account(f"buddy-reapprove-two-{suffix}@example.com")
    first = create_student(first_account["id"], "Ari", 3, 7)
    second = create_student(second_account["id"], "Bo", 5, 9)

    request = create_request(first["id"], second["id"])
    approve_request(request["id"], first_account["id"], True)
    declined = approve_request(request["id"], second_account["id"], False)
    assert declined["status"] == "declined"

    approved_again = approve_request(request["id"], second_account["id"], True)
    assert approved_again["status"] == "active"
    assert is_buddy(first["id"], second["id"])


def test_parent_removing_an_active_buddy_removes_the_shared_relationship() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    first_account = ensure_account(f"buddy-remove-one-{suffix}@example.com")
    second_account = ensure_account(f"buddy-remove-two-{suffix}@example.com")
    first = create_student(first_account["id"], "Ari", 3, 7)
    second = create_student(second_account["id"], "Bo", 5, 9)
    request = create_request(first["id"], second["id"])
    approve_request(request["id"], first_account["id"], True)
    approve_request(request["id"], second_account["id"], True)
    assert is_buddy(first["id"], second["id"])

    removed = remove_buddy_for_parent(first_account["id"], request["id"])
    assert removed == {"removed": True}
    assert not is_buddy(first["id"], second["id"])

    reopened = approve_request(request["id"], first_account["id"], True)
    assert reopened["status"] == "pending"
    restored = approve_request(request["id"], second_account["id"], True)
    assert restored["status"] == "active"
    assert is_buddy(first["id"], second["id"])


def test_buddy_headers_use_the_same_child_navigation_as_progress() -> None:
    playtime = (ROOT / "static/playtime.html").read_text(encoding="utf-8")
    customise = (ROOT / "static/character-customise.html").read_text(encoding="utf-8")
    buddy_script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")

    for page in (playtime, customise):
        assert 'class="header"' in page
        assert 'class="header-content"' in page
        assert 'class="nav-links"' in page
        assert 'id="parent-dashboard-link"' in page
        assert 'id="home-login-link"' in page
        assert 'id="home-logout-link"' in page
        assert '/static/js/auth-nav.js' in page
    assert "function addProgressHeader()" in buddy_script
    assert "'/static/js/auth-nav.js?v=20260905-kid-header-1'" in buddy_script


def test_parent_dashboard_study_buddy_link_has_a_real_in_page_target() -> None:
    dashboard = (ROOT / "static/parent_dashboard.html").read_text(encoding="utf-8")

    assert 'href="/parent-dashboard#study-buddies"' in dashboard
    assert '<section id="study-buddy-parent-panel" class="section"' in dashboard
    assert dashboard.index('id="study-buddy-parent-panel"') < dashboard.index("</main>")


def test_study_buddies_has_a_child_friendly_style_and_app_shortcut() -> None:
    page = (ROOT / "static/study-buddies.html").read_text(encoding="utf-8")
    app = (ROOT / "static/app.html").read_text(encoding="utf-8")
    style = (ROOT / "static/css/study-buddies.css").read_text(encoding="utf-8")

    assert "study-buddies.css" in page
    assert "study-buddies.css" in app
    assert 'class="study-buddies-quick-access"' in app
    assert 'href="/study-buddies"' in app
    assert "data-study-buddies-page-link" in app
    assert ".buddy-hero" in style
    assert 'href="/app"' in (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in style


def test_buddy_code_and_find_buddy_are_together_above_the_buddy_list() -> None:
    script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")
    style = (ROOT / "static/css/study-buddies.css").read_text(encoding="utf-8")

    assert 'class="buddy-get-started"' in script
    assert script.index("My Buddy Code") < script.index("Find a buddy") < script.index("My buddies")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in style
    assert ".buddy-get-started { grid-template-columns: 1fr; }" in style


def test_buddy_controls_keep_search_and_actions_on_one_line() -> None:
    script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")
    style = (ROOT / "static/css/study-buddies.css").read_text(encoding="utf-8")

    assert 'class="buddy-search-controls"' in script
    assert "grid-template-columns: minmax(0, 1fr) auto" in style
    assert ".buddy-actions { display: flex; align-items: center;" in style
    assert ".buddy-emoji-actions { display: flex; gap: 6px; flex-wrap: nowrap;" in style


def test_parent_dashboard_replaces_a_repeat_approval_with_waiting_status() -> None:
    dashboard = (ROOT / "static/parent_dashboard.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/parent-dashboard.js").read_text(encoding="utf-8")

    assert "const currentParentApproved" in dashboard
    assert "You approved — waiting for the other parent." in dashboard
    assert "Approve again" in dashboard
    assert "Delete buddy" in dashboard
    assert "function removeBuddy(request)" in dashboard
    assert "title.textContent = `${requesterName} ↔ ${targetName}`;" in dashboard
    assert "Child: ${requesterName}" in dashboard
    assert "Add buddy again" in dashboard
    assert "child-sign-in-button" in dashboard
    catalog_actions = script[script.index("async function loadCatalog"):script.index("async function loadGiftRequests")]
    assert "requestPassword" not in catalog_actions
    assert "parent_password" not in catalog_actions


def test_parent_dashboard_session_actions_do_not_repeat_password_prompts() -> None:
    script = (ROOT / "static/js/parent-dashboard.js").read_text(encoding="utf-8")
    routes = (ROOT / "src/webapp/parent_dashboard_routes.py").read_text(encoding="utf-8")
    reward_routes = (ROOT / "src/webapp/reward_routes.py").read_text(encoding="utf-8")

    assert "parent_password: password" not in script[script.index("function decideGift"):script.index("async function openStudyPlan")]
    assert "parent_password: password" not in script[script.index("byId('catalog-form')"):script.index("byId('summary-frequency')")]
    assert "requestPassword(async (password)" not in script[script.index("byId('send-digest-button')"):script.index("byId('cancel-password')")]
    assert "class XpDigestRequest" not in routes
    assert "class GiftRequestDecision(BaseModel):\n    parent_password" not in routes
    assert "class CatalogItemRequest(BaseModel):\n    name" in reward_routes
    assert "xp_cost: int = Field(default=100, ge=10, le=5000)\n    parent_password" not in reward_routes


def test_approved_buddies_can_send_fixed_kind_emojis_via_buddy_code() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    first_account = ensure_account(f"buddy-one-{suffix}@example.com")
    second_account = ensure_account(f"buddy-two-{suffix}@example.com")
    first = create_student(first_account["id"], "River", 3, 7)
    second = create_student(second_account["id"], "Sky", 3, 7)

    # A Buddy Code finds one known learner; a nickname cannot search children.
    assert find_students(second["buddy_code"].lower(), first["id"])[0]["student_id"] == second["id"]
    assert find_students("Sky", first["id"]) == []
    assert find_students(second["kid_code"], first["id"]) == []
    assert find_students(f"{second['buddy_code'][:-4]}-{second['buddy_code'][-4:]}", first["id"]) == []
    assert re.fullmatch(r"SKY\d{4}", second["buddy_code"])
    assert second["buddy_code"] != second["kid_code"]


    request = create_request(first["id"], second["id"])
    approve_request(request["id"], first_account["id"], True)
    approve_request(request["id"], second_account["id"], True)
    assert is_buddy(first["id"], second["id"])

    sent = send_emoji_reaction(first["id"], second["id"], "heart")
    received = emoji_reactions_for(second["id"])
    assert sent["symbol"] == EMOJI_OPTIONS["heart"]["emoji"]
    assert received[0]["emoji"] == EMOJI_OPTIONS["heart"]["emoji"]
    assert received[0]["sender_student_id"] == first["id"]
    assert DAILY_EMOJI_SEND_LIMIT == 40


def test_challenge_list_identifies_the_buddy_who_sent_and_receives_it() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    sender_account = ensure_account(f"buddy-challenge-sender-{suffix}@example.com")
    receiver_account = ensure_account(f"buddy-challenge-receiver-{suffix}@example.com")
    sender = create_student(sender_account["id"], "Robin", 3, 7)
    receiver = create_student(receiver_account["id"], "Sky", 3, 7)
    request = create_request(sender["id"], receiver["id"])
    approve_request(request["id"], sender_account["id"], True)
    approve_request(request["id"], receiver_account["id"], True)
    create_challenge(sender["id"], receiver["id"], "maths")

    received = challenges_for(receiver["id"])[0]
    sent = challenges_for(sender["id"])[0]

    assert received["requester_nickname"] == "Robin"
    assert received["target_nickname"] == "You"
    assert sent["requester_nickname"] == "You"
    assert sent["target_nickname"] == "Sky"
    assert received["target_year_group"] == 3
    assert received["practice_subject"] == "Maths"


def test_open_challenges_are_listed_before_completed_challenges() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    sender_account = ensure_account(f"buddy-challenge-order-sender-{suffix}@example.com")
    receiver_account = ensure_account(f"buddy-challenge-order-receiver-{suffix}@example.com")
    sender = create_student(sender_account["id"], "Robin", 3, 7)
    receiver = create_student(receiver_account["id"], "Sky", 3, 7)
    request = create_request(sender["id"], receiver["id"])
    approve_request(request["id"], sender_account["id"], True)
    approve_request(request["id"], receiver_account["id"], True)
    completed = create_challenge(sender["id"], receiver["id"], "maths")
    open_challenge = create_challenge(sender["id"], receiver["id"], "english")
    with _engine().begin() as conn:
        conn.execute(
            update(buddy_challenges)
            .where(buddy_challenges.c.id == completed["id"])
            .values(status="completed")
        )

    challenges = challenges_for(receiver["id"])
    assert challenges[0]["id"] == open_challenge["id"]
    assert challenges[0]["status"] == "open"


def test_buddy_completion_rewards_both_children_and_queues_one_celebration() -> None:
    from src.webapp.reward_store import get_reward_store

    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    sender_account = ensure_account(f"buddy-reward-sender-{suffix}@example.com")
    receiver_account = ensure_account(f"buddy-reward-receiver-{suffix}@example.com")
    sender = create_student(sender_account["id"], "Robin", 4, 8)
    receiver = create_student(receiver_account["id"], "Sky", 4, 8)
    request = create_request(sender["id"], receiver["id"])
    approve_request(request["id"], sender_account["id"], True)
    approve_request(request["id"], receiver_account["id"], True)
    challenge = create_challenge(sender["id"], receiver["id"], "eleven_plus_maths")

    get_reward_store().award_checked_activity(
        account_id=receiver_account["id"], student_id=receiver["id"],
        fingerprint="a" * 64, subject="11+ Maths", accuracy=1,
    )
    completed = complete_challenge_for_verified_activity(
        challenge_id=challenge["id"], student_id=receiver["id"], subject="11+ Maths",
        accuracy=1.0,
    )

    assert completed is not None
    assert completed["reward"]["awarded_xp"] == challenge["xp_reward"] * 2
    assert completed["buddy_reward"]["awarded_gift_points"] == challenge["gift_points_reward"] * 2
    assert completed["awarded_xp"] == challenge["xp_reward"] * 2
    notices = challenge_completion_notifications_for(sender["id"])
    assert len(notices) == 1
    assert notices[0]["buddy_nickname"] == "Sky"
    assert acknowledge_challenge_completion_notification(notices[0]["id"], sender["id"]) == {"acknowledged": True}
    assert challenge_completion_notifications_for(sender["id"]) == []


def test_study_buddy_page_requires_a_kid_session_and_places_picker_by_the_button() -> None:
    script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")
    style = (ROOT / "static/css/study-buddies.css").read_text(encoding="utf-8")

    assert "A child needs to sign in with their code" in script
    assert "Sign in as your child" in script
    assert "click “Open child sign-in” next to their Child login code" in script
    assert "The code will be ready on the next page" in script
    assert "/parent-dashboard#family-title" in script
    assert "Child sign-in switches this browser to your child’s learning space." in script
    assert "/kid-login?next=/study-buddies" in script
    assert "actionArea.append(picker)" in script
    assert "requester_nickname" in script and "target_nickname" in script
    assert ".buddy-challenge-row" in style


def test_sending_a_buddy_emoji_has_a_child_friendly_sent_animation() -> None:
    script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")
    style = (ROOT / "static/css/study-buddies.css").read_text(encoding="utf-8")

    assert "sendEmoji(buddy.student_id, option.key, emojiButton)" in script
    assert "function animateSentEmoji(sourceButton, emoji)" in script
    assert "buddy-emoji-flight" in script
    assert "Sent!" in script
    assert ".buddy-emoji-flight" in style
    assert "@keyframes buddy-emoji-fly" in style
    assert "buddy-emoji-flight-reduced" in style


def test_admin_configured_buddy_limit_blocks_new_connections() -> None:
    from src.webapp.study_buddy_store import get_study_buddy_settings

    init_study_buddy_db()
    original = get_study_buddy_settings()["max_buddies_per_learner"]
    suffix = uuid4().hex[:12]
    try:
        set_max_buddies_per_learner(1)
        account_a = ensure_account(f"buddy-limit-a-{suffix}@example.com")
        account_b = ensure_account(f"buddy-limit-b-{suffix}@example.com")
        account_c = ensure_account(f"buddy-limit-c-{suffix}@example.com")
        first = create_student(account_a["id"], "Ava", 3, 7)
        second = create_student(account_b["id"], "Ben", 3, 7)
        third = create_student(account_c["id"], "Cam", 3, 7)

        request = create_request(first["id"], second["id"])
        approve_request(request["id"], account_a["id"], True)
        approve_request(request["id"], account_b["id"], True)

        with pytest.raises(ValueError, match="up to 1 Study Buddies"):
            create_request(first["id"], third["id"])
    finally:
        set_max_buddies_per_learner(original)


def test_startup_replaces_a_dashed_development_buddy_code() -> None:
    init_study_buddy_db()
    suffix = uuid4().hex[:12]
    owner_account = ensure_account(f"buddy-legacy-owner-{suffix}@example.com")
    requester_account = ensure_account(f"buddy-legacy-requester-{suffix}@example.com")
    owner = create_student(owner_account["id"], "Legacy", 3, 7)
    requester = create_student(requester_account["id"], "Robin", 3, 7)
    with _engine().begin() as conn:
        conn.execute(
            update(students)
            .where(students.c.id == owner["id"])
            .values(buddy_code="LEGACY-5470")
        )

    init_study_buddy_db()
    refreshed = get_student(owner["id"])

    assert refreshed["buddy_code"] == "LEGACY5470"
    assert find_students("LEGACY5470", requester["id"])[0]["student_id"] == owner["id"]
    assert find_students("LEGACY-5470", requester["id"]) == []
