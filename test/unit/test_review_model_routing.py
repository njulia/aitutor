"""Regression tests for quick/detail model routing."""
from __future__ import annotations

import uuid

from src.webapp import review_service


class RecordingLLM:
    provider = "api"
    model = "default-model"

    def __init__(self) -> None:
        self.models: list[str | None] = []

    def complete(self, messages, temperature=None, max_tokens=None, model=None):
        self.models.append(model)
        return "Helpful feedback. Score: 1/1"


def unique_question() -> str:
    return f"What is 1 + 1? Ref {uuid.uuid4().hex}"


def test_model_defaults() -> None:
    assert review_service.QUICK_REVIEW_MODEL == "deepseek-v4-flash"
    assert review_service.DETAIL_REVIEW_MODEL == "gemini-3.6-flash"


def test_explicit_quick_review_uses_quick_model() -> None:
    llm = RecordingLLM()
    review_service.review_homework(
        unique_question(), "2", "Maths", {"year_group": 3},
        quick_review=True, llm_client=llm,
    )
    assert llm.models == [review_service.QUICK_REVIEW_MODEL]


def test_other_review_uses_detail_model() -> None:
    llm = RecordingLLM()
    review_service.review_homework(
        unique_question(), "2", "Maths", {"year_group": 3}, llm_client=llm
    )
    assert llm.models == [review_service.DETAIL_REVIEW_MODEL]


def test_rag_quick_review_uses_trusted_local_marking_without_model(monkeypatch) -> None:
    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_: [{"question": "What is 1 + 1?", "answer": "2"}],
    )
    llm = RecordingLLM()
    result = review_service.review_homework(
        unique_question(), "2", "Maths", {"year_group": 3},
        quick_review=True,
        homework_doc_id=f"rag-{uuid.uuid4().hex}",
        llm_client=llm,
    )

    assert result["from_rag_answers"] is True
    assert result["llm_fallback"] is True
    assert result["model_used"] is None
    assert llm.models == []


def test_review_question_uses_detail_model() -> None:
    llm = RecordingLLM()
    review_service.review_homework(
        unique_question(), "2", "Maths", {"year_group": 3},
        is_tutor_mode=True, llm_client=llm,
    )
    assert llm.models == [review_service.DETAIL_REVIEW_MODEL]


def test_year_round_review_uses_detail_model() -> None:
    llm = RecordingLLM()
    review_service.review_homework(
        unique_question(), "2", "Maths-1year",
        {"year_group": 5, "plan_week": 12}, llm_client=llm,
    )
    assert llm.models == [review_service.DETAIL_REVIEW_MODEL]


def test_explain_and_improve_use_detail_model() -> None:
    llm = RecordingLLM()
    question = unique_question()
    review_service.explain_deep(
        question, "2", "Maths", {"year_group": 3}, llm_client=llm
    )
    review_service.improve_practice(
        question, "2", "Maths", {"year_group": 3}, llm_client=llm
    )
    assert llm.models == [
        review_service.DETAIL_REVIEW_MODEL,
        review_service.DETAIL_REVIEW_MODEL,
    ]
