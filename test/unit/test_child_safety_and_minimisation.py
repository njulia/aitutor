from __future__ import annotations

from unittest.mock import MagicMock

from src.webapp.child_safety import detect_safeguarding_concern
from src.webapp.prompt_budget import budget_review_inputs, minimise_personal_data
from src.webapp import review_service


def test_explicit_first_person_danger_is_intercepted() -> None:
    concern = detect_safeguarding_concern("I am not safe. Someone keeps hurting me.")
    assert concern is not None
    assert concern.category == "abuse_or_immediate_danger"
    assert "trusted adult" in concern.message
    assert "999" in concern.message
    assert "0800 1111" in concern.message


def test_story_or_curriculum_text_does_not_trigger_safeguarding() -> None:
    assert detect_safeguarding_concern("The character says he wants to die in the story.") is None
    assert detect_safeguarding_concern("Explain why someone might feel unsafe in wartime.") is None


def test_review_pauses_before_calling_the_model() -> None:
    llm = MagicMock()
    result = review_service.review_homework(
        "1. Write one sentence.",
        "I want to hurt myself",
        "English",
        {"year_group": 4, "age": 8},
        llm_client=llm,
    )
    assert result["safety_intervention"] is True
    assert result["model_tier"] == "none"
    llm.complete.assert_not_called()


def test_clear_identifiers_are_removed_but_math_numbers_remain() -> None:
    raw = (
        "My email is pupil@example.com. My postcode is SW1A 1AA. "
        "My phone number is 07123 456789. Answer: 07123456789."
    )
    safe = minimise_personal_data(raw)
    assert "pupil@example.com" not in safe
    assert "SW1A 1AA" not in safe
    assert "07123 456789" not in safe
    assert "07123456789" in safe


def test_llm_budget_uses_minimised_text() -> None:
    budget = budget_review_inputs(
        "Email pupil@example.com and solve 12 + 5.",
        "My name is Ana Smith. The answer is 17.",
        {"year_group": 2, "age": 7, "student_id": "private"},
    )
    assert "pupil@example.com" not in budget["homework_content"]
    assert "Ana Smith" not in budget["student_answers"]
    assert budget["profile"] == {"year_group": 2, "age": 7}
