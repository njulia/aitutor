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


def test_review_with_rag_answer_calls_detail_llm(monkeypatch) -> None:
    from src.webapp import review_service

    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_: [{"question": "1. What is 2 + 2?", "answer": "4"}],
    )
    llm = MagicMock()
    llm.provider = "api"
    llm.model = "default-model"
    llm.complete.return_value = "## What You Did Well\nYou used addition accurately."

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
    assert llm.complete.call_args.kwargs["model"] == review_service.DETAIL_REVIEW_MODEL
    assert "addition accurately" in result["review"]


def test_generator_skips_more_than_first_fifty_seen_candidates(monkeypatch, tmp_path) -> None:
    """Regression: a learner must reach row 51 instead of falling back to the LLM."""
    import src.homework_generator as generator

    assignment_store = HomeworkAssignmentStore(f"sqlite+pysqlite:///{tmp_path / 'many.db'}")
    all_candidates = [
        {"doc_id": f"doc_{index:03d}", "content": f"{index}. Question", "metadata": {}}
        for index in range(1, 61)
    ]
    for item in all_candidates[:50]:
        assignment_store.record(
            "learner_many",
            item["doc_id"],
            subject="Maths",
            year_group=2,
            content_kind="primary",
        )

    def metadata_search(*, year_group, subject, k, exclude_ids=None, **_):
        assert year_group == 2
        assert subject == "Maths"
        excluded = set(exclude_ids or [])
        return [item for item in all_candidates if item["doc_id"] not in excluded][:k]

    monkeypatch.setattr(generator, "get_assignment_store", lambda: assignment_store)
    monkeypatch.setattr(generator, "search_homework_by_metadata", metadata_search)

    llm = MagicMock()
    llm.complete.side_effect = AssertionError("LLM must not run while row 51 is unseen")
    result = generator.generate_homework_for_subject(
        {"student_id": "learner_many", "year_group": 2, "age": 6},
        "Maths",
        llm,
    )

    assert result == ("51. Question", "doc_051", True)
    llm.complete.assert_not_called()
