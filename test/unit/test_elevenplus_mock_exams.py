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
                "herschel.slough.sch.uk",
                "wilsons.school",
                "tiffingirls.org",
                "saintolaves.net",
                "athenatuition.co.uk",
                "hbschool.org.uk",
                "bright-futures.co.uk",
                "reading-school.co.uk",
                "cchs.co.uk",
            )
        )


def test_expanded_catalogue_preserves_initial_mocks_and_question_bank() -> None:
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

    assert len(mocks.EXAMS) == 29
    assert len(mocks._QUESTIONS) == 278
    assert expected_new_exams <= set(mocks.EXAMS)
    assert all(not mocks.EXAMS[exam_id]["is_free"] for exam_id in expected_new_exams)
    assert {
        mocks.EXAMS[exam_id]["last_verified"] for exam_id in expected_new_exams
    } == {"2026-08-06"}

    for prefix in ("m", "e", "v", "n"):
        assert {
            f"{prefix}{number:02d}" for number in range(17, 49)
        } <= set(mocks._QUESTION_BY_ID)


def test_catalogue_adds_two_more_common_public_source_mocks() -> None:
    expected_new_common = {
        "common-full-7": "Common Four-Subject Mock G",
        "common-full-8": "Common Four-Subject Mock H",
    }

    for exam_id, title in expected_new_common.items():
        exam = mocks.EXAMS[exam_id]
        assert exam["title"] == title
        assert exam["category"] == "common"
        assert exam["stage"] == "Full practice"
        assert exam["is_free"] is False
        assert exam["last_verified"] == "2026-08-09"
        assert exam["source_ids"] == ("dfe-primary", "common-four-subject")
        assert len(exam["question_ids"]) == 32

        subjects = Counter(
            mocks._QUESTION_BY_ID[question_id]["subject"]
            for question_id in exam["question_ids"]
        )
        assert subjects == {
            "Maths": 8,
            "English": 8,
            "Verbal Reasoning": 8,
            "Non-Verbal Reasoning": 8,
        }
        assert Counter(
            mocks._QUESTION_BY_ID[question_id]["answer"]
            for question_id in exam["question_ids"]
        ) == {"A": 8, "B": 8, "C": 8, "D": 8}

    for prefix in ("m", "e", "v", "n"):
        assert {
            f"{prefix}{number:02d}" for number in range(49, 65)
        } <= set(mocks._QUESTION_BY_ID)


def test_catalogue_adds_five_public_source_area_target_mocks() -> None:
    expected_new_targets = {
        "bexley-selection-1": "bexley-selection-2027",
        "wirral-assessment-1": "wirral-assessment-2027",
        "gloucestershire-grammar-1": "gloucestershire-test-2027",
        "slough-consortium-1": "slough-consortium-2027",
        "medway-test-1": "medway-test-2027",
    }

    for exam_id, source_id in expected_new_targets.items():
        exam = mocks.EXAMS[exam_id]
        assert exam["category"] == "school_target"
        assert exam["is_free"] is False
        assert exam["last_verified"] == "2026-08-09"
        assert source_id in exam["source_ids"]
        assert source_id in mocks.PUBLIC_SOURCES
        assert "official" in exam["format_note"].casefold() or "published" in exam["format_note"].casefold()


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
        "bexley-selection-1": {
            "English",
            "Maths",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
        },
        "wirral-assessment-1": {
            "Maths",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
        },
        "gloucestershire-grammar-1": {
            "English",
            "Maths",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
        },
        "slough-consortium-1": {
            "English",
            "Maths",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
        },
        "medway-test-1": {
            "English",
            "Maths",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
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


def test_catalogue_adds_only_the_seven_supported_new_school_targets() -> None:
    expected_new_targets = {
        "wilsons-second-stage-1": ("Wilson's School", "wilsons-second-stage-2027"),
        "tiffin-girls-stage-one-1": ("The Tiffin Girls' School", "tiffin-girls-2027"),
        "st-olaves-stage-one-1": ("St Olave's Grammar School", "st-olaves-2027"),
        "henrietta-barnett-first-round-1": (
            "The Henrietta Barnett School",
            "henrietta-barnett-2027",
        ),
        "altrincham-girls-1": (
            "Altrincham Grammar School for Girls",
            "altrincham-girls-2027",
        ),
        "reading-fsce-1": ("Reading School", "reading-fsce-2027"),
        "cchs-fsce-1": (
            "Chelmsford County High School for Girls",
            "cchs-fsce-2027",
        ),
    }

    assert sum(
        exam["category"] == "school_target" for exam in mocks.EXAMS.values()
    ) == 20
    for exam_id, (school, source_id) in expected_new_targets.items():
        exam = mocks.EXAMS[exam_id]
        assert exam["school"] == school
        assert exam["category"] == "school_target"
        assert exam["is_free"] is False
        assert exam["last_verified"] == "2026-08-09"
        assert source_id in exam["source_ids"]
        assert source_id in mocks.PUBLIC_SOURCES
        assert "official" in exam["format_note"].casefold()

    locked = {
        exam["id"]: exam
        for exam in mocks.mock_exam_catalogue(has_mock_access=False)["exams"]
    }
    unlocked = {
        exam["id"]: exam
        for exam in mocks.mock_exam_catalogue(has_mock_access=True)["exams"]
    }
    assert all(not locked[exam_id]["available"] for exam_id in expected_new_targets)
    assert all(unlocked[exam_id]["available"] for exam_id in expected_new_targets)


def test_new_school_targets_match_published_subject_scopes() -> None:
    traditional_scopes = {
        "wilsons-second-stage-1": {"English", "Maths"},
        "tiffin-girls-stage-one-1": {"English", "Maths"},
        "st-olaves-stage-one-1": {
            "English",
            "Maths",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
        },
        "henrietta-barnett-first-round-1": {
            "English",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
        },
        "altrincham-girls-1": {
            "Maths",
            "Verbal Reasoning",
            "Non-Verbal Reasoning",
        },
    }
    fsce_scope = {
        "Art & Design",
        "Computing",
        "Design & Technology",
        "English",
        "Geography",
        "History",
        "Languages",
        "Maths",
        "Music",
        "Physical Education",
        "Science",
    }

    for exam_id, expected in traditional_scopes.items():
        assert {
            mocks._QUESTION_BY_ID[question_id]["subject"]
            for question_id in mocks.EXAMS[exam_id]["question_ids"]
        } == expected
    for exam_id in ("reading-fsce-1", "cchs-fsce-1"):
        assert {
            mocks._QUESTION_BY_ID[question_id]["subject"]
            for question_id in mocks.EXAMS[exam_id]["question_ids"]
        } == fsce_scope

    for exam_id in (*traditional_scopes, "reading-fsce-1", "cchs-fsce-1"):
        positions = Counter(
            mocks._QUESTION_BY_ID[question_id]["answer"]
            for question_id in mocks.EXAMS[exam_id]["question_ids"]
        )
        assert set(positions) == {"A", "B", "C", "D"}
        assert max(positions.values()) - min(positions.values()) <= 1

    assert len([item for item in mocks._QUESTIONS if item["id"].startswith("fsce")]) == 22
    assert "not multiple choice" in mocks.EXAMS["wilsons-second-stage-1"]["format_note"]
    assert "creative response" in mocks.EXAMS["reading-fsce-1"]["format_note"]
    assert "other answer formats" in mocks.EXAMS["cchs-fsce-1"]["format_note"]


def test_pates_and_kegs_are_not_duplicated_because_shared_tests_already_exist() -> None:
    pates_coverage = mocks.EXAMS["gloucestershire-grammar-1"]
    kegs_coverage = mocks.EXAMS["csse-essex-1"]

    assert pates_coverage["school"] == "Gloucestershire grammar schools"
    assert "gloucestershire-test-2027" in pates_coverage["source_ids"]
    assert kegs_coverage["school"] == "CSSE selective schools in Essex"
    assert "csse-2027" in kegs_coverage["source_ids"]
    assert not any(
        exam["school"] in {
            "Pate's Grammar School",
            "King Edward VI Grammar School Chelmsford",
        }
        for exam in mocks.EXAMS.values()
    )


def test_new_school_targets_start_securely_and_score_locally(monkeypatch) -> None:
    monkeypatch.setenv("SESSION_OWNER_SECRET", "unit-test-secret-that-is-long-enough-123")
    exam_ids = (
        "wilsons-second-stage-1",
        "tiffin-girls-stage-one-1",
        "st-olaves-stage-one-1",
        "henrietta-barnett-first-round-1",
        "altrincham-girls-1",
        "reading-fsce-1",
        "cchs-fsce-1",
    )

    for index, exam_id in enumerate(exam_ids):
        identity = f"learner-{index}"
        started = mocks.start_mock_exam(exam_id, identity, now=10_000)
        assert not _contains_private_key(started)
        assert len(started["questions"]) == len(mocks.EXAMS[exam_id]["question_ids"])

        result = mocks.score_mock_exam(
            exam_id,
            started["attempt"]["token"],
            identity,
            _all_correct(exam_id),
            now=10_100,
        )
        assert result["score"]["percent"] == 100
        assert result["recommended_topics"] == []


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


def test_attempt_start_accepts_secret_manager_value_over_blake2_key_limit(
    monkeypatch,
) -> None:
    # ``openssl rand -base64 48`` produces 64 visible characters. When its
    # newline is stored too, the value is 65 bytes and raw BLAKE2b rejects it.
    monkeypatch.setenv("SESSION_OWNER_SECRET", ("A" * 64) + "\n")

    started = mocks.start_mock_exam("common-diagnostic-1", "learner-a", now=1_000)
    result = mocks.score_mock_exam(
        "common-diagnostic-1",
        started["attempt"]["token"],
        "learner-a",
        _all_correct("common-diagnostic-1"),
        now=1_100,
    )

    assert started["success"] is True
    assert result["score"]["percent"] == 100


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


def test_start_response_matches_frontend_contract(monkeypatch) -> None:
    """返回的 JSON 形状必须与 mock-exams.js 中 startExam 所期望的完全一致。"""
    monkeypatch.setenv("SESSION_OWNER_SECRET", "unit-test-secret-that-is-long-enough-123")
    result = mocks.start_mock_exam("common-diagnostic-1", "learner-a", now=1_000)

    # data.success
    assert result["success"] is True

    # data.exam --- JS: state.exam = data.exam; examTitle = state.exam.title
    exam = result["exam"]
    assert isinstance(exam["id"], str) and len(exam["id"]) > 0
    assert isinstance(exam["title"], str) and len(exam["title"]) > 0
    assert isinstance(exam["duration_minutes"], int) and exam["duration_minutes"] > 0
    assert isinstance(exam["question_count"], int) and exam["question_count"] > 0

    # data.questions --- JS: state.questions = data.questions || []
    questions = result["questions"]
    assert isinstance(questions, list) and len(questions) > 0
    first = questions[0]
    assert isinstance(first["id"], str) and len(first["id"]) > 0
    assert isinstance(first["subject"], str) and len(first["subject"]) > 0
    assert isinstance(first["topic"], str) and len(first["topic"]) > 0
    assert isinstance(first["prompt"], str) and len(first["prompt"]) > 0
    # options: [{label, text}] --- JS: option.label, option.text
    assert isinstance(first["options"], list) and len(first["options"]) >= 2
    opt = first["options"][0]
    assert isinstance(opt["label"], str) and len(opt["label"]) == 1
    assert isinstance(opt["text"], str) and len(opt["text"]) > 0

    # data.attempt --- JS: state.attemptToken = data.attempt.token; state.deadline = Number(data.attempt.deadline)
    attempt = result["attempt"]
    assert isinstance(attempt["token"], str) and len(attempt["token"]) > 20
    assert isinstance(attempt["deadline"], int) and attempt["deadline"] > attempt.get("started_at", 0)
    assert isinstance(attempt["started_at"], int)
