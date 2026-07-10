from src.webapp.question_utils import (
    _parse_student_answers_to_map,
    _split_homework_into_questions,
    normalize_question,
)


def test_normalize_question_removes_common_number_formats():
    expected = "1 + 2 = ?"
    assert normalize_question("1. 1 + 2 = ?") == expected
    assert normalize_question("1) 1 + 2 = ?") == expected
    assert normalize_question("(1) 1 + 2 = ?") == expected
    assert normalize_question("Question 1: 1 + 2 = ?") == expected


def test_normalize_question_collapses_whitespace_and_case():
    assert normalize_question("  QUESTION 2.   What   Is  3 + 4? ") == "what is 3 + 4?"


def test_split_numbered_homework_assigns_stable_zero_based_indexes():
    questions = _split_homework_into_questions(
        "Maths practice\n1. 1 + 2 = ?\n2. 5 - 3 = ?",
        "Maths",
    )

    assert [q["content"] for q in questions] == ["1 + 2 = ?", "5 - 3 = ?"]
    assert [q["full_content"] for q in questions] == ["1. 1 + 2 = ?", "2. 5 - 3 = ?"]
    assert [q["question_index"] for q in questions] == [0, 1]
    assert all(q["subject"] == "Maths" for q in questions)
    assert len({q["question_id"] for q in questions}) == 2


def test_split_bulleted_homework():
    questions = _split_homework_into_questions("- Name a noun\n- Name a verb", "English")
    assert [q["content"] for q in questions] == ["Name a noun", "Name a verb"]
    assert [q["question_index"] for q in questions] == [0, 1]


def test_split_unnumbered_homework_as_one_question():
    questions = _split_homework_into_questions("What is 8 divided by 2?", "Maths")
    assert len(questions) == 1
    assert questions[0]["content"] == "What is 8 divided by 2?"
    assert questions[0]["question_index"] == 0


def test_parse_numbered_student_answers_maps_to_rag_questions():
    rag_questions = ["1. 1 + 2 = ?", "2. 5 - 3 = ?"]
    answer_map = _parse_student_answers_to_map("1. 3\n2. 2", "Maths", rag_questions)
    assert answer_map == {
        "1. 1 + 2 = ?": "3",
        "2. 5 - 3 = ?": "2",
    }


def test_parse_single_tutor_answer_maps_to_only_question():
    rag_questions = ["4. 9 - 5 = ?"]
    answer_map = _parse_student_answers_to_map("4", "Maths", rag_questions)
    assert answer_map == {"4. 9 - 5 = ?": "4"}
