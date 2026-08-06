"""Contracts for the original, locally scored 11+ mock-exam engine."""
from __future__ import annotations

from collections import Counter
import re
from urllib.parse import urlparse

import pytest

from src import elevenplus_mock_exams as mocks


pytestmark = pytest.mark.unit


def _all_correct(exam_id: str) -> dict[str, str]:
    return {
        question_id: mocks._QUESTION_BY_ID[question_id]["answer"]
        for question_id in mocks.EXAMS[exam_id]["question_ids"]
    }


def _contains_private_key(value) -> bool:
    if isinstance(value, dict):
        return any(
            key in {"answer", "correct_answer", "explanation"}
            or _contains_private_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_private_key(item) for item in value)
    return False


def test_catalogue_separates_common_and_school_target_mocks_without_answers() -> None:
    catalogue = mocks.mock_exam_catalogue(has_mock_access=False)

    assert {item["category"] for item in catalogue["exams"]} == {
        "common",
        "school_target",
    }
    free_exams = [item for item in catalogue["exams"] if item["is_free"]]
    assert [(item["id"], item["title"]) for item in free_exams] == [
        ("common-diagnostic-1", "Common 11+ Diagnostic")
    ]
    assert free_exams[0]["available"] is True
    assert free_exams[0]["required_plan"] is None
    assert any(not item["is_free"] and not item["available"] for item in catalogue["exams"])
    assert all(
        item["required_plan"] == "elevenplus_monthly"
        and item["required_plan_name"] == "11+ Premium"
        for item in catalogue["exams"]
        if not item["is_free"]
    )
    assert not _contains_private_key(catalogue)

    unlocked = mocks.mock_exam_catalogue(has_mock_access=True)
    assert all(item["available"] for item in unlocked["exams"])
    assert all(
        item["required_plan"] == "elevenplus_monthly"
        for item in unlocked["exams"]
        if not item["is_free"]
    )


def test_every_exam_is_unique_and_uses_only_declared_public_sources() -> None:
    mocks.validate_mock_exam_content()
    exam_sets = [tuple(exam["question_ids"]) for exam in mocks.EXAMS.values()]

    assert len(exam_sets) == len(set(exam_sets))
    for source in mocks.PUBLIC_SOURCES.values():
        parsed = urlparse(source["url"])
        assert parsed.scheme == "https"
        assert parsed.netloc.endswith(
            (
                "gov.uk",
                "warwickshire.gov.uk",
                "qebarnet.co.uk",
                "tiffinschool.co.uk",
                "kent.gov.uk",
                "buckinghamshire.gov.uk",
                "greenshaw.co.uk",
                "westmidlandsgrammarschools.co.uk",
                "csse.org.uk",
                "lrgs.org.uk",
            )
        )


def test_expanded_catalogue_has_ten_new_mocks_and_128_new_questions() -> None:
    expected_new_exams = {
        "common-full-3",
        "common-full-4",
        "buckinghamshire-transfer-1",
        "kent-test-1",
        "sutton-set-1",
        "common-full-5",
        "common-full-6",
        "west-midlands-grammar-1",
        "csse-essex-1",
        "lancaster-royal-grammar-1",
    }

    assert len(mocks.EXAMS) == 15
    assert len(mocks._QUESTIONS) == 192
    assert expected_new_exams <= set(mocks.EXAMS)
    assert all(not mocks.EXAMS[exam_id]["is_free"] for exam_id in expected_new_exams)
    assert {
        mocks.EXAMS[exam_id]["last_verified"] for exam_id in expected_new_exams
    } == {"2026-08-06"}

    for prefix in ("m", "e", "v", "n"):
        assert {
            f"{prefix}{number:02d}" for number in range(17, 49)
        } <= set(mocks._QUESTION_BY_ID)


def test_new_area_target_mocks_match_their_declared_subject_scope() -> None:
    expected_subjects = {
        "buckinghamshire-transfer-1": {
            "English",
            "Verbal Reasoning",
            "Maths",
            "Non-Verbal Reasoning",
        },
        "kent-test-1": {
            "English",
            "Verbal Reasoning",
            "Maths",
            "Non-Verbal Reasoning",
        },
        "sutton-set-1": {"English", "Maths"},
        "west-midlands-grammar-1": {
            "English",
            "Verbal Reasoning",
            "Maths",
            "Non-Verbal Reasoning",
        },
        "csse-essex-1": {"English", "Maths"},
        "lancaster-royal-grammar-1": {
            "English",
            "Maths",
            "Verbal Reasoning",
        },
    }

    for exam_id, subjects in expected_subjects.items():
        exam = mocks.EXAMS[exam_id]
        actual = {
            mocks._QUESTION_BY_ID[question_id]["subject"]
            for question_id in exam["question_ids"]
        }
        assert actual == subjects
        assert exam["category"] == "school_target"
        assert exam["is_free"] is False


def test_validation_rejects_reordered_duplicate_exam_content(monkeypatch) -> None:
    duplicate = dict(mocks.EXAMS["common-full-5"])
    duplicate["id"] = "reordered-duplicate"
    duplicate["question_ids"] = tuple(reversed(duplicate["question_ids"]))
    monkeypatch.setitem(mocks.EXAMS, duplicate["id"], duplicate)

    with pytest.raises(ValueError, match="repeats the question set"):
        mocks.validate_mock_exam_content()


def test_paid_common_full_mocks_do_not_repeat_questions() -> None:
    common_full_exams = [
        set(exam["question_ids"])
        for exam in mocks.EXAMS.values()
        if exam["category"] == "common"
        and not exam["is_free"]
        and exam["stage"] == "Full practice"
    ]

    assert len(common_full_exams) >= 2
    for index, question_ids in enumerate(common_full_exams):
        for later_ids in common_full_exams[index + 1:]:
            assert question_ids.isdisjoint(later_ids)


def test_anagram_questions_have_exactly_one_matching_option() -> None:
    for question in mocks._QUESTIONS:
        if question["topic"] != "Anagrams":
            continue
        source_word = re.findall(r"\b[A-Z]{4,}\b", question["prompt"])[-1]
        source_letters = Counter(source_word)
        matching_labels = {
            option["label"]
            for option in question["options"]
            if Counter(re.sub(r"[^A-Z]", "", option["text"].upper())) == source_letters
        }
        assert matching_labels == {question["answer"]}, question["id"]


def test_started_attempt_hides_answers_and_is_bound_to_its_learner(monkeypatch) -> None:
    monkeypatch.setenv("SESSION_OWNER_SECRET", "unit-test-secret-that-is-long-enough-123")
    started = mocks.start_mock_exam("common-diagnostic-1", "learner-a", now=1_000)

    assert started["attempt"]["deadline"] == 1_900
    assert all("answer" not in question for question in started["questions"])
    assert all("explanation" not in question for question in started["questions"])

    result = mocks.score_mock_exam(
        "common-diagnostic-1",
        started["attempt"]["token"],
        "learner-a",
        _all_correct("common-diagnostic-1"),
        now=1_100,
    )
    assert result["score"]["percent"] == 100
    assert result["score"]["correct"] == result["score"]["total"]
    assert result["recommended_topics"] == []

    with pytest.raises(mocks.InvalidAttempt, match="different learner"):
        mocks.score_mock_exam(
            "common-diagnostic-1",
            started["attempt"]["token"],
            "learner-b",
            {},
            now=1_100,
        )


def test_submission_reports_unanswered_topics_and_enforces_grace_period(monkeypatch) -> None:
    monkeypatch.setenv("SESSION_OWNER_SECRET", "unit-test-secret-that-is-long-enough-123")
    started = mocks.start_mock_exam("common-diagnostic-1", "learner-a", now=2_000)

    result = mocks.score_mock_exam(
        "common-diagnostic-1",
        started["attempt"]["token"],
        "learner-a",
        {"m01": "B"},
        now=2_100,
    )
    assert result["score"]["answered"] == 1
    assert result["score"]["unanswered"] == 11
    assert len(result["subject_breakdown"]) == 4
    assert 1 <= len(result["recommended_topics"]) <= 4
    assert all("correct_answer" in question for question in result["questions"])

    with pytest.raises(mocks.ExpiredAttempt):
        mocks.score_mock_exam(
            "common-diagnostic-1",
            started["attempt"]["token"],
            "learner-a",
            {},
            now=started["attempt"]["deadline"] + 901,
        )
