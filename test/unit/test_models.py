import pytest
from pydantic import ValidationError

from src.webapp.models import ReviewRequest


def test_review_request_accepts_zero_based_question_index():
    request = ReviewRequest(
        homework="1 + 2 = ?",
        answers="3",
        is_tutor_mode=True,
        from_rag=True,
        homework_doc_id="doc-1",
        question_index=0,
    )
    assert request.question_index == 0


def test_review_request_rejects_negative_question_index():
    with pytest.raises(ValidationError):
        ReviewRequest(homework="1 + 2 = ?", answers="3", question_index=-1)
