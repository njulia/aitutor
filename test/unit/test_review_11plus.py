from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.webapp.review_service import review_homework

def test_review_homework_11plus_context_preservation():
    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "Excellent work!"

    homework_content = "Solve the multi-step equation: (43 × 4) - 34 = ?"
    student_answers = "D"
    subject = "Maths"
    
    # We need to mock format_prompt to see what it receives, 
    # OR we can mock build_messages if we want to see the final prompt.
    # But since review_service.py imports format_prompt locally, we'll patch it.
    
    with patch("src.llm_client.format_prompt") as mock_format:
        mock_format.return_value = "Mocked Prompt"
        
        review_homework(
            homework_content=homework_content,
            student_answers=student_answers,
            subject=subject,
            is_eleven_plus=True,
            llm_client=mock_llm
        )
        
        # Verify format_prompt was called with the correct 'question' argument
        args, kwargs = mock_format.call_args
        assert "question" in kwargs
        assert homework_content in kwargs["question"]
        assert student_answers in kwargs["question"]
        assert "Question:" in kwargs["question"]
        assert "Student Answer:" in kwargs["question"]

def test_review_homework_non_11plus_behavior():
    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "Good job!"

    homework_content = "What is 2 + 2?"
    student_answers = "4"
    subject = "Maths"
    
    with patch("src.llm_client.format_prompt") as mock_format:
        mock_format.return_value = "Mocked Prompt"
        
        review_homework(
            homework_content=homework_content,
            student_answers=student_answers,
            subject=subject,
            is_eleven_plus=False,
            llm_client=mock_llm
        )
        
        args, kwargs = mock_format.call_args
        assert "question" in kwargs
        # In non-11plus mode, it should only be the student answer (budgeted)
        assert kwargs["question"] == student_answers
