from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.webapp import review_service


def test_no_rag_11plus_review_uses_quick_prompt_with_age_bounded_profile() -> None:
    mock_llm = MagicMock()
    mock_llm.provider = "api"
    mock_llm.model = "default-model"
    mock_llm.complete.return_value = "## Score\n**1/1**"

    with patch("src.llm_client.format_prompt", return_value="Mocked Prompt") as mock_format:
        result = review_service.review_homework(
            homework_content="Solve the multi-step equation: (43 × 4) - 34 = ?",
            student_answers="138",
            subject="Maths",
            profile={"student_id": "private-id", "year_group": 99, "age": 99},
            is_eleven_plus=True,
            quick_review=True,
            llm_client=mock_llm,
        )

    _, kwargs = mock_format.call_args
    assert kwargs["homework_content"].startswith("Solve the multi-step equation")
    assert kwargs["student_answer"] == "138"
    assert "private-id" not in kwargs["student_profile"]
    assert "'year_group': 6" in kwargs["student_profile"]
    assert "'age': 11" in kwargs["student_profile"]
    assert result["success"] is True


def test_no_rag_primary_review_uses_local_ollama_model_and_integer_tokens() -> None:
    mock_llm = MagicMock()
    mock_llm.provider = "ollama"
    mock_llm.model = "deepseek-v4-flash"
    mock_llm.complete.return_value = "## Score\n**1/1**"

    with patch("src.llm_client.format_prompt", return_value="Mocked Prompt"):
        review_service.review_homework(
            homework_content="What is 2 + 2?",
            student_answers="4",
            subject="Maths",
            is_eleven_plus=False,
            quick_review=True,
            llm_client=mock_llm,
        )

    call_kwargs = mock_llm.complete.call_args.kwargs
    assert call_kwargs["model"] == "deepseek-v4-flash"
    assert isinstance(call_kwargs["max_tokens"], int)
    assert call_kwargs["max_tokens"] <= 1600


def test_rag_wrong_answer_is_reviewed_by_detail_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_: [
            {
                "question": "1. What is 9 + 6?",
                "answer": "15",
                "explanation": "Make 10 by moving 1 from 6 to 9, then add the remaining 5.",
            }
        ],
    )
    mock_llm = MagicMock()
    mock_llm.provider = "api"
    mock_llm.model = "default-model"
    mock_llm.complete.return_value = "## What to Improve\nUse the make-ten method, then check the total."

    result = review_service.review_homework(
        homework_content="1. What is 9 + 6?",
        student_answers="14",
        subject="Maths-1year",
        profile={"year_group": 5, "age": 10},
        homework_doc_id="week-1",
        is_eleven_plus=True,
        llm_client=mock_llm,
    )

    assert result["success"] is True
    assert result["correct_count"] == 0
    assert "15" in result["review"]
    assert "make-ten method" in result["review"]
    assert result["model_used"] == review_service.DETAIL_REVIEW_MODEL
    assert mock_llm.complete.call_args.kwargs["model"] == review_service.DETAIL_REVIEW_MODEL
