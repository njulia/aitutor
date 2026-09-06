"""Contract tests for Study Buddy challenge subject coverage."""
from __future__ import annotations

import json

from src.models import ELEVEN_PLUS_SUBJECTS, UK_PRIMARY_SUBJECTS
from src.webapp.study_buddy_challenge_catalog import (
    ADVANCED_CHALLENGE_REWARD,
    CHALLENGE_CATALOG,
    NORMAL_CHALLENGE_REWARD,
    canonical_challenge_subject,
    challenge_catalog_entry,
    challenge_catalog_options,
    challenge_subject_matches,
    is_eleven_plus_activity_subject,
    legacy_open_target_count_types,
    supported_challenge_types,
)


def test_catalogue_covers_every_learning_app_primary_subject() -> None:
    primary_options = [
        option
        for option in CHALLENGE_CATALOG.values()
        if option["group"] == "primary" and option["subject"] in UK_PRIMARY_SUBJECTS
    ]

    assert {option["subject"] for option in primary_options} == set(UK_PRIMARY_SUBJECTS)
    assert all(option["practice_tab"] == "homework" for option in primary_options)


def test_catalogue_has_a_valid_challenge_path_for_every_11_plus_subject() -> None:
    for subject in ELEVEN_PLUS_SUBJECTS:
        recorded_subject = f"11+ {subject}"
        assert any(
            challenge_subject_matches(challenge_type, recorded_subject)
            for challenge_type in supported_challenge_types()
        ), subject


def test_catalogue_options_are_small_one_activity_rewards_and_api_safe() -> None:
    options = challenge_catalog_options()

    assert options
    assert {option["key"] for option in options} == set(CHALLENGE_CATALOG)
    assert all(option["target_count"] == 1 for option in options)
    assert all(option["xp"] > 0 and option["gift_points"] > 0 for option in options)
    assert all(option["icon"] and option["label"] and option["title"] for option in options)
    assert all(option["practice_subject"] for option in options)
    assert {option["practice_tab"] for option in options} <= {"homework", "eleven"}
    assert all(option["xp"] == NORMAL_CHALLENGE_REWARD["xp"] for option in options if option["group"] == "primary")
    assert all(option["xp"] == ADVANCED_CHALLENGE_REWARD["xp"] for option in options if option["group"] == "eleven_plus")
    eleven_options = [option for option in options if option["group"] == "eleven_plus"]
    assert all("11+" in option["label"] for option in eleven_options)
    json.dumps(options)


def test_catalogue_accepts_only_known_keys_and_never_falls_back_to_mixed() -> None:
    assert challenge_catalog_entry("science")["subject"] == "Science"
    assert challenge_catalog_entry("DESIGN-TECHNOLOGY")["key"] == "design_technology"
    assert challenge_catalog_entry("not-a-real-subject") is None
    assert challenge_catalog_entry("") is None


def test_subject_matching_is_exact_for_supported_subjects_and_11_plus() -> None:
    assert canonical_challenge_subject("d&t") == "Design and Technology"
    assert canonical_challenge_subject("11+ Maths") == "Maths"
    assert challenge_subject_matches("science", "Science")
    assert challenge_subject_matches("french", "French")
    assert not challenge_subject_matches("science", "History")
    assert challenge_subject_matches("verbal_reasoning", "11+ Verbal Reasoning")
    assert not challenge_subject_matches("verbal_reasoning", "Non-Verbal Reasoning")
    assert challenge_subject_matches("11plus", "11+ Maths")
    assert challenge_subject_matches("11plus", "Verbal Reasoning")
    assert not challenge_subject_matches("11plus", "Maths")
    assert challenge_subject_matches("eleven_plus_maths", "11+ Maths")
    assert not challenge_subject_matches("eleven_plus_maths", "Maths")
    assert challenge_subject_matches("mixed", "Arabic")
    assert not challenge_subject_matches("mixed", "Anything")
    assert not challenge_subject_matches("not-a-real-subject", "Maths")
    assert is_eleven_plus_activity_subject("11+ English")
    assert not is_eleven_plus_activity_subject("English")


def test_legacy_upgrade_scope_is_narrow_and_preserves_new_subject_types() -> None:
    assert legacy_open_target_count_types() == {
        "maths", "english", "reasoning", "11plus", "mixed"
    }
    assert "science" not in legacy_open_target_count_types()
    assert "verbal_reasoning" not in legacy_open_target_count_types()
