from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_received_buddy_challenges_link_to_the_right_learning_area() -> None:
    script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")
    stylesheet = (ROOT / "static/css/study-buddies.css").read_text(encoding="utf-8")

    assert "function practiceDestinationFor(challenge)" in script
    assert "practice_subject" in script
    assert "practice_tab" in script
    assert "primarySubjectsByKey" in script
    assert "elevenPlusSubjectsByKey" in script
    assert "buddy_challenge=${encodeURIComponent(challengeId)}" in script
    assert "target_year_group" in script
    assert "const yearQuery" in script
    assert "`/app?tab=${encodeURIComponent(tab)}${subjectQuery}${yearQuery}${challengeQuery}`" in script
    assert "challengePracticeLink(challenge)" in script
    assert "▶ ${destination.label}" in script
    assert "label: subject ? `Start ${tab === 'eleven' ? '11+ ' : ''}${subject}`" in script
    assert "Start ${validYear ? `Year ${requestedYear} `" not in script
    assert ".buddy-challenge-start" in stylesheet


def test_challenge_picker_accepts_server_catalogue_entries_with_a_safe_fallback() -> None:
    script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")

    assert "function availableChallengeTypes()" in script
    assert "state.challenge_options || state.challenge_types || state.challenge_catalog" in script
    assert "return options.length ? options : defaultChallengeTypes;" in script
    assert "Homework subjects" in script
    assert "11+ subjects" in script


def test_rankings_are_side_by_side_and_buddy_completions_have_a_safe_popup() -> None:
    script = (ROOT / "static/js/study-buddies-v2.js").read_text(encoding="utf-8")
    style = (ROOT / "static/css/study-buddies.css").read_text(encoding="utf-8")

    assert 'class="buddy-ranking-columns"' in script
    assert "weekly-ranking-title" in script and "all-time-ranking-title" in script
    assert "buddy_completion_notifications" in script
    assert "function showCompletionDialog" in script
    assert "challenge-notifications/${encodeURIComponent(notification.id)}/seen" in script
    assert ".buddy-ranking-columns" in style
    assert ".buddy-completion-dialog" in style
    assert "Claim reward" not in script
    assert "Finish this subject activity to earn both rewards automatically." in script
    assert "up to +${challenge.xp_reward * 2} XP" in script


def test_started_buddy_challenge_is_completed_automatically_after_answer_checking() -> None:
    app_script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    server = (ROOT / "web_app.py").read_text(encoding="utf-8")
    store = (ROOT / "src/webapp/study_buddy_store.py").read_text(encoding="utf-8")

    assert "function activeStudyBuddyChallengeId()" in app_script
    assert app_script.count("study_buddy_challenge_id: activeStudyBuddyChallengeId()") >= 3
    assert "complete_challenge_for_verified_activity" in server
    assert "accuracy=accuracy" in server
    assert "multiplier = 1.0 + score" in store
