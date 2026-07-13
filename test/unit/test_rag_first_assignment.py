from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from src.webapp.homework_assignment_store import HomeworkAssignmentStore

pytestmark = pytest.mark.unit


def test_assignment_claim_is_unique_under_concurrency(tmp_path) -> None:
    store = HomeworkAssignmentStore(f"sqlite+pysqlite:///{tmp_path / 'assignments.db'}")

    def claim() -> str | None:
        return store.claim_first_unseen(
            "learner_123",
            ["doc_a", "doc_b"],
            subject="Maths",
            year_group=1,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: claim(), range(2)))

    assert set(claimed) == {"doc_a", "doc_b"}
    assert store.seen_doc_ids("learner_123") == {"doc_a", "doc_b"}


def test_generator_uses_unseen_rag_before_llm(monkeypatch, tmp_path) -> None:
    import src.homework_generator as generator

    store = HomeworkAssignmentStore(f"sqlite+pysqlite:///{tmp_path / 'generator.db'}")
    candidates = [
        {"doc_id": "doc_1", "content": "1. What is 1 + 1?", "metadata": {}},
        {"doc_id": "doc_2", "content": "1. What is 2 + 2?", "metadata": {}},
    ]
    monkeypatch.setattr(generator, "get_assignment_store", lambda: store)
    monkeypatch.setattr(generator, "search_homework_by_metadata", lambda **_: candidates)
    monkeypatch.setattr(generator, "get_student_previous_topics", lambda *_: [])

    llm = MagicMock()
    llm.complete.side_effect = AssertionError("LLM must not run while unseen RAG homework exists")
    profile = {"student_id": "learner_456", "year_group": 1, "age": 5}

    first = generator.generate_homework_for_subject(profile, "Maths", llm)
    second = generator.generate_homework_for_subject(profile, "Maths", llm)

    assert first == ("1. What is 1 + 1?", "doc_1", True)
    assert second == ("1. What is 2 + 2?", "doc_2", True)
    llm.complete.assert_not_called()


def test_review_with_rag_answer_does_not_call_llm(monkeypatch) -> None:
    from src.webapp import review_service

    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_: [{"question": "1. What is 2 + 2?", "answer": "4"}],
    )
    llm = MagicMock()
    llm.complete.side_effect = AssertionError("LLM must not mark an authoritative RAG answer")

    result = review_service.review_homework(
        "1. What is 2 + 2?",
        "4",
        "Maths",
        {"student_id": "learner_789", "year_group": 1, "age": 5},
        homework_doc_id="doc_math",
        is_tutor_mode=True,
        question_index=0,
        llm_client=llm,
    )

    assert result["success"] is True
    assert result["from_rag_answers"] is True
    assert result["correct_count"] == 1
    llm.complete.assert_not_called()
