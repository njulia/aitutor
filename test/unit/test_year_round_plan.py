from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


LEGACY_WEEK = """11+ Maths 52-Week Plan - Term 1 - Week 1
Topic Focus: Place value
Syllabus: Number
Objectives:
- Read place values

Homework Question 1:
Which is 1,000 + 500?
Options: 1,400, 1,500, 1,600, 2,000, 500
Correct Answer: B (1,500)
Explanation: Add five hundreds to ten hundreds to make fifteen hundreds.
Coaching Strategy: Line up the place values before choosing.

Homework Question 2:
Which sentence is correctly punctuated?
Options: "I'm ready," said James., "I'm ready" said James., Other, Fourth, Fifth
Correct Answer: A ("I'm ready," said James.)
Explanation: The comma belongs inside the closing speech mark.
Coaching Strategy: Read the spoken words aloud first.
"""


def test_legacy_year_round_content_becomes_answer_free_questions() -> None:
    from src.elevenplus_rag import (
        extract_year_round_answer_records,
        format_questions_only,
        questions_from_answer_records,
    )

    records = extract_year_round_answer_records(LEGACY_WEEK)
    assert len(records) == 2
    assert records[0]["options"] == ["1,400", "1,500", "1,600", "2,000", "500"]
    assert records[1]["options"][0] == '"I\'m ready," said James.'

    questions = questions_from_answer_records(records)
    public_text = format_questions_only(questions)
    assert len(questions) == 2
    assert questions[0]["number"] == 1
    assert questions[0]["options"][1] == {"label": "B", "text": "1,500"}
    assert "Correct Answer" not in public_text
    assert "Explanation:" not in public_text
    assert "Coaching Strategy:" not in public_text


def test_weekly_generation_uses_hard_week_filter_before_semantic_search(monkeypatch, tmp_path) -> None:
    import src.homework_generator as generator
    from src.webapp.homework_assignment_store import HomeworkAssignmentStore

    assignment_store = HomeworkAssignmentStore(f"sqlite+pysqlite:///{tmp_path / 'weekly.db'}")
    calls = []

    def metadata_search(**kwargs):
        calls.append(kwargs)
        return [{"doc_id": "week_14", "content": "QUESTIONS\n1. Pick one.\nA) One\nB) Two", "metadata": {}}]

    monkeypatch.setattr(generator, "get_assignment_store", lambda: assignment_store)
    monkeypatch.setattr(generator, "elevenplus_search_homework_by_metadata", metadata_search)
    monkeypatch.setattr(
        generator,
        "elevenplus_search_homework",
        lambda **_: (_ for _ in ()).throw(AssertionError("semantic search must not run for a selected week")),
    )
    monkeypatch.setattr(generator, "elevenplus_get_student_previous_topics", lambda *_: [])

    llm = MagicMock()
    llm.complete.side_effect = AssertionError("LLM must not run when the correct weekly RAG item exists")
    profile = {
        "student_id": "learner_weekly",
        "year_group": 5,
        "age": 10,
        "plan_week": 14,
        "learning_goals": ["Decimals and percentages"],
    }
    result = generator.generate_homework_for_subject(
        profile,
        "Maths-1year",
        llm,
        is_eleven_plus=True,
    )
    repeated = generator.generate_homework_for_subject(
        profile,
        "Maths-1year",
        llm,
        is_eleven_plus=True,
    )

    assert result == ("QUESTIONS\n1. Pick one.\nA) One\nB) Two", "week_14", True)
    assert repeated == result
    assert calls == [{
        "year_group": 6,
        "subject": "Maths-1year",
        "week_num": 14,
        "content_type": "year_round",
        "k": 20,
    }] * 2
    llm.complete.assert_not_called()


def test_subject_alias_prefers_new_year_round_key_and_keeps_legacy_records(monkeypatch) -> None:
    import src.elevenplus_rag as rag

    class FakeStore:
        def __init__(self):
            self.filters = []

        def search_by_metadata(self, filters, k):
            self.filters.append(filters)
            if filters["subject"] == "VerbalReasoning-1year":
                return [{"doc_id": "new_vr", "content": "new", "metadata": filters}]
            return []

    store = FakeStore()
    monkeypatch.setattr(rag, "get_elevenplus_rag_store", lambda: store)
    results = rag.search_homework_by_metadata(
        6,
        "VerbalReasoning-1year",
        week_num=7,
        content_type="year_round",
        k=10,
    )

    assert [item["doc_id"] for item in results] == ["new_vr"]
    assert store.filters == [{
        "year_group": 6,
        "subject": "VerbalReasoning-1year",
        "week_num": 7,
        "content_type": "year_round",
    }]


def test_subject_alias_can_fall_back_to_old_vr_key(monkeypatch) -> None:
    import src.elevenplus_rag as rag

    class FakeStore:
        def __init__(self):
            self.filters = []

        def search_by_metadata(self, filters, k):
            self.filters.append(filters)
            if filters["subject"] == "VerbalReasoning":
                return [{"doc_id": "legacy_vr", "content": "legacy", "metadata": filters}]
            return []

    store = FakeStore()
    monkeypatch.setattr(rag, "get_elevenplus_rag_store", lambda: store)
    results = rag.search_homework_by_metadata(6, "VerbalReasoning-1year", week_num=7, k=10)

    assert [item["doc_id"] for item in results] == ["legacy_vr"]
    assert [item["subject"] for item in store.filters] == [
        "VerbalReasoning-1year",
        "Verbal Reasoning-1year",
        "Verbal Reasoning",
        "VerbalReasoning",
    ]


def test_rag_marking_uses_detail_llm_with_answer_key_context(monkeypatch) -> None:
    from src.webapp import review_service

    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_: [
            {
                "question": "1. Which is 1,000 + 500?",
                "answer": "1,500",
                "correct_letter": "B",
                "explanation": "Add five hundreds to ten hundreds to make fifteen hundreds.",
                "tip": "Line up the place values.",
            }
        ],
    )
    llm = MagicMock()
    llm.provider = "api"
    llm.model = "default-model"
    llm.complete.return_value = "## Explanation for Every Answer\nAdd the hundreds carefully."

    result = review_service.review_homework(
        "QUESTIONS\n1. Which is 1,000 + 500?\nA) 1,400\nB) 1,500",
        "1. 1,500",
        "Maths-1year",
        {"student_id": "weekly_review", "year_group": 5, "age": 10},
        homework_doc_id="week_01",
        is_eleven_plus=True,
        is_tutor_mode=True,
        llm_client=llm,
    )

    assert result["correct_count"] == 1
    assert "Add the hundreds carefully" in result["review"]
    assert llm.complete.call_args.kwargs["model"] == review_service.DETAIL_REVIEW_MODEL
    prompt_messages = llm.complete.call_args.args[0]
    assert "Add five hundreds" in prompt_messages[0]["content"]
    assert "1,500" in prompt_messages[0]["content"]
