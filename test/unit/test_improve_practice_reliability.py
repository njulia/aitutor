from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.webapp import review_service

pytestmark = pytest.mark.unit


class ResultLLM:
    provider = "api"
    model = "test-model"

    def __init__(self, result):
        self.result = result

    def complete(self, *_args, **_kwargs):
        return self.result


def _question() -> str:
    return f"1. What is 4 + 3? Reference {uuid.uuid4().hex}"


@pytest.mark.parametrize("empty_result", [None, "", "   ", "None", "null", "{}", "[]"])
def test_empty_model_result_is_not_reported_as_success(empty_result) -> None:
    result = review_service.improve_practice(
        _question(),
        "1. 6",
        "Maths",
        {"year_group": 3, "age": 7},
        llm_client=ResultLLM(empty_result),
    )

    assert result["success"] is False
    assert result["llm_no_response"] is True
    assert "did not return any usable practice questions" in result["error"]


def test_explanation_without_questions_is_rejected() -> None:
    result = review_service.improve_practice(
        _question(),
        "1. 6",
        "Maths",
        {"year_group": 3, "age": 7},
        llm_client=ResultLLM("Revise number bonds carefully and keep trying."),
    )

    assert result["success"] is False
    assert result["llm_no_response"] is True


def test_numbered_model_questions_are_returned_in_a_renderable_shape() -> None:
    practice = """## Similar Practice Questions
1. What is 5 + 4?
2. What is 6 + 3?
3. What is 7 + 2?

## Quick Revision Notes
Remember to count on from the larger number.
"""
    result = review_service.improve_practice(
        _question(),
        "1. 6",
        "Maths",
        {"year_group": 3, "age": 7},
        llm_client=ResultLLM(practice),
    )

    assert result["success"] is True
    assert result["practice"].startswith("## Similar Practice Questions")
    assert len(result["questions"]) == 3


def test_browser_handles_empty_practice_and_displays_visible_message() -> None:
    source = Path("static/js/app.js").read_text(encoding="utf-8")

    assert "const practiceContent = String(data.practice || '').trim();" in source
    assert "showPracticeGenerationMessage(errorMsg);" in source
    assert "panel.setAttribute('role', 'alert');" in source
    assert "question_index: Number.isInteger(reviewContext.question_index)" in source

