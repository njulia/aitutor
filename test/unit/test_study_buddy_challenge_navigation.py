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
