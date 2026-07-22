from __future__ import annotations

from unittest.mock import MagicMock

from src.ui import shared
from src.webapp import review_service


def test_common_profile_is_parsed_locally_without_false_art_match() -> None:
    llm = MagicMock()
    llm.complete_json.side_effect = AssertionError("Common profile should not use the LLM")

    profile = shared.parse_profile_from_natural_language(
        "Ana is a 7-year-old student in Year 2 in London. She has a particular interest in mathematics.",
        llm,
    )

    assert profile is not None
    assert profile["year_group"] == 2
    assert profile["age"] == 7
    assert profile["extracted_subjects"] == ["Maths"]
    llm.complete_json.assert_not_called()


def test_profile_fallback_removes_identity_before_llm(monkeypatch) -> None:
    captured = {}

    def fake_format(_template, **kwargs):
        captured.update(kwargs)
        return "safe prompt"

    llm = MagicMock()
    llm.complete_json.return_value = {
        "year_group": 4,
        "age": 8,
        "extracted_subjects": ["Science"],
    }
    monkeypatch.setattr(shared, "format_prompt", fake_format)

    profile = shared.parse_profile_from_natural_language(
        "Molly is curious in London. Parent email: parent.unique@example.com. She enjoys puzzles.",
        llm,
    )

    assert profile is not None
    safe_description = captured["description"]
    assert "Molly" not in safe_description
    assert "parent.unique@example.com" not in safe_description
    assert "London" not in safe_description
    assert profile["student_id"] == "custom_student"


def test_detailed_rag_explanation_is_local_and_child_friendly(monkeypatch) -> None:
    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_: [
            {
                "question": "1. Which is one half?",
                "answer": "0.5",
                "correct_letter": "B",
                "explanation": "One half means one of two equal parts. As a decimal, that is 0.5.",
                "tip": "Link one half, 50%, and 0.5.",
            }
        ],
    )
    llm = MagicMock()
    llm.provider = "api"
    llm.model = "default-model"
    llm.complete.return_value = "## What to Improve\nConnect one half with 0.5, then check the option."

    result = review_service.explain_deep(
        "1. Which is one half?\nA) 0.2\nB) 0.5",
        "1. 0.2",
        "Maths-1year",
        {"year_group": 5, "age": 10},
        homework_doc_id="week-2",
        is_eleven_plus=True,
        llm_client=llm,
    )

    assert result["success"] is True
    assert result["model_tier"] == "plus"
    assert "Connect one half with 0.5" in result["explanation"]
    assert "One half means one of two equal parts" in result["explanation"]
    assert llm.complete.call_args.kwargs["model"] == review_service.DETAIL_REVIEW_MODEL
    prompt_messages = llm.complete.call_args.args[0]
    assert "One half means one of two equal parts" not in prompt_messages[0]["content"]
    assert "Link one half, 50%, and 0.5" not in prompt_messages[0]["content"]
