from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_guided_profile_is_bounded_and_non_identifying(app_module) -> None:
    profile = app_module.normalise_guided_eleven_profile(
        {
            "setup_source": "guided_11plus",
            "year_group": 2,
            "subject": "English",
            "confidence": "needs_help",
            "question_count": 99,
            "exam_format": "GL Assessment",
            "exam_date": "2026-09-12",
            "learning_notes": "Email child@example.com. Comprehension is tricky.",
            "target_school": "This field must not be retained",
            "description": "This legacy field must not be retained",
        },
        "learner_opaque",
    )

    assert profile["year_group"] == 3
    assert profile["age"] == 8
    assert profile["subject"] == "English"
    assert profile["question_count"] == 8
    assert profile["confidence"] == "needs_help"
    assert profile["exam_month"] == "September 2026"
    assert "child@example.com" not in profile["learning_needs"]
    assert "[email removed]" in profile["learning_needs"]
    assert "target_school" not in profile
    assert "description" not in profile

    client_profile = app_module.guided_eleven_client_profile(profile)
    assert "student_id" not in client_profile
    assert "learning_needs" not in client_profile
    assert "weak_areas" not in client_profile
    assert client_profile["question_count"] == 8


def test_public_question_limit_keeps_only_answer_free_questions(app_module) -> None:
    questions = [
        {
            "number": index,
            "question": f"Question {index}?",
            "response_type": "single_choice",
            "options": [
                {"label": "A", "text": "First"},
                {"label": "B", "text": "Second"},
            ],
        }
        for index in range(1, 9)
    ]
    results = [{
        "subject": "Maths",
        "content": "original full content",
        "questions": questions,
        "doc_id": "eleven_doc",
        "from_rag": True,
    }]

    limited = app_module.limit_homework_question_count(results, 5)

    assert len(limited[0]["questions"]) == 5
    assert [item["number"] for item in limited[0]["questions"]] == [1, 2, 3, 4, 5]
    assert "Question 5?" in limited[0]["content"]
    assert "Question 6?" not in limited[0]["content"]
    assert "answer" not in limited[0]["content"].lower()
    assert len(results[0]["questions"]) == 8


def test_guided_frontend_replaces_long_child_profile_and_does_not_send_school() -> None:
    html = Path("static/app.html").read_text(encoding="utf-8")
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")

    assert 'id="eleven-profile"' not in html
    assert 'id="eleven-guide-question"' in html
    assert "Plan 11+ practice with me" in html
    assert "not sent to the AI" in html

    function_body = javascript.split(
        "async function generateCustomHomeworkEleven()", 1
    )[1].split("function formatQuestions", 1)[0]
    assert "target_school:" not in function_body
    assert "question_count:" in function_body
    assert "setup_source: 'guided_11plus'" in function_body
    save_choices_body = javascript.split(
        "function saveLearningChoices()", 1
    )[1].split("function restoreLearningChoices()", 1)[0]
    assert "eleven-parent-notes" not in save_choices_body


def test_guided_frontend_persists_minutes_and_migrates_old_question_counts() -> None:
    html = Path("static/app.html").read_text(encoding="utf-8")
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")

    assert "const ELEVEN_SESSION_QUESTIONS" in javascript
    assert "10: 5" in javascript
    assert "15: 8" in javascript

    save_choices_body = javascript.split(
        "function saveLearningChoices()", 1
    )[1].split("function restoreLearningChoices()", 1)[0]
    assert "value.elevenMinutes = elevenMinutes" in save_choices_body
    assert "delete value.elevenQuestionCount" in save_choices_body

    restore_choices_body = javascript.split(
        "function restoreLearningChoices()", 1
    )[1].split("function applyLandingPagePreset()", 1)[0]
    assert "legacyElevenQuestionCount === 5" in restore_choices_body
    assert "legacyElevenQuestionCount === 8" in restore_choices_body
    assert "elevenGuideState.answers.session_minutes = elevenMinutes" in restore_choices_body

    generate_body = javascript.split(
        "async function generateCustomHomeworkEleven()", 1
    )[1].split("function formatQuestions", 1)[0]
    assert "const questionCount = ELEVEN_SESSION_QUESTIONS[sessionMinutes]" in generate_body
    assert "question_count: questionCount" in generate_body
    assert "Number(answers.question_count)" not in generate_body
    assert "11plus-saved-plan" in html
