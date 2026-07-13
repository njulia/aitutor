from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_public_question_model_supports_mixed_primary_homework() -> None:
    from src.webapp.question_utils import parse_public_questions

    content = """Year 3 Maths
1. What is 6 × 4?
A) 20
B) 24
C) 28
2. Write the next multiple of 5 after 35.
3. Pick the odd number. A) 12 B) 17 C) 20
"""
    questions = parse_public_questions(content)

    assert [item["response_type"] for item in questions] == [
        "single_choice",
        "text",
        "single_choice",
    ]
    assert questions[0]["options"][1] == {"label": "B", "text": "24"}
    assert questions[1]["options"] == []
    assert questions[2]["options"][1]["text"] == "17"


def test_public_question_model_hides_answer_and_explanation_sections() -> None:
    from src.webapp.question_utils import parse_public_questions

    content = """QUESTIONS
1. Which decimal is equal to one half?
A) 0.2
B) 0.5
C) 2.0

ANSWERS
1. B

EXPLANATIONS
One half is five tenths.
"""
    questions = parse_public_questions(content)

    assert len(questions) == 1
    serialised = repr(questions)
    assert "ANSWERS" not in serialised
    assert "One half is five tenths" not in serialised
    assert questions[0]["options"][1]["text"] == "0.5"


def test_legacy_options_line_is_converted_to_labelled_choices() -> None:
    from src.webapp.question_utils import parse_public_questions

    content = """Homework Question 1:
Which word is spelled correctly?
Options: receive, recieve, receeve
Correct Answer: A (receive)
Explanation: i before e does not apply after c.
"""
    questions = parse_public_questions(content)

    assert questions == [
        {
            "number": 1,
            "question": "Which word is spelled correctly?",
            "response_type": "single_choice",
            "options": [
                {"label": "A", "text": "receive"},
                {"label": "B", "text": "recieve"},
                {"label": "C", "text": "receeve"},
            ],
        }
    ]


def test_tutor_split_preserves_single_choice_metadata() -> None:
    from src.webapp.question_utils import _split_homework_into_questions

    items = _split_homework_into_questions(
        "1. Choose the prime number.\nA) 8\nB) 11\nC) 12\n2. What is 9 + 4?",
        "Maths",
    )

    assert len(items) == 2
    assert items[0]["response_type"] == "single_choice"
    assert items[0]["options"][1]["text"] == "11"
    assert items[1]["response_type"] == "text"
    assert items[1]["questions"][0]["question"] == "What is 9 + 4?"


def test_shared_passages_are_attached_to_the_questions_that_need_them() -> None:
    from src.webapp.question_utils import parse_public_questions

    content = """Read this passage carefully.
Tom found a silver key under the old oak tree.

1. Where did Tom find the key?
A) In a box
B) Under the oak tree

2. What colour was the key?
A) Gold
B) Silver

Read the second passage.
Maya counted twelve stars.

3. How many stars did Maya count?
A) Ten
B) Twelve
"""
    questions = parse_public_questions(content)

    assert "Tom found a silver key" in questions[0]["context"]
    assert "context" not in questions[1]
    assert "Maya counted twelve stars" in questions[2]["context"]
