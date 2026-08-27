from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_guided_homework_profile_is_bounded_and_non_identifying(app_module) -> None:
    profile = app_module.normalise_guided_homework_profile(
        {
            "setup_source": "guided_homework",
            "year_group": 4,
            "subject": "Chinese",
            "session_minutes": 20,
            "difficulty": "challenge",
            "learning_notes": (
                "Email pupil@example.com. My school is Example Primary. "
                "Fractions are tricky."
            ),
            "description": "This legacy field must not be retained.",
            "target_school": "This field must not be retained.",
        },
        "learner_opaque",
    )

    assert profile["year_group"] == 4
    assert profile["age"] == 9
    assert profile["subject"] == "Chinese"
    assert profile["preferred_session_minutes"] == 20
    assert profile["question_count"] == 10
    assert profile["difficulty"] == "challenge"
    assert "pupil@example.com" not in profile["learning_needs"]
    assert "[email removed]" in profile["learning_needs"]
    assert "Example Primary" not in profile["learning_needs"]
    assert "description" not in profile
    assert "target_school" not in profile

    client_profile = app_module.guided_homework_client_profile(profile)
    assert "student_id" not in client_profile
    assert "learning_needs" not in client_profile
    assert client_profile["subject"] == "Chinese"
    assert client_profile["preferred_session_minutes"] == 20


def test_guided_homework_profile_uses_safe_defaults(app_module) -> None:
    profile = app_module.normalise_guided_homework_profile(
        {
            "year_group": 99,
            "subject": "Cryptocurrency",
            "session_minutes": 90,
            "difficulty": "impossible",
        },
        "learner_opaque",
    )

    assert profile["year_group"] == 6
    assert profile["subject"] == "Maths"
    assert profile["preferred_session_minutes"] == 15
    assert profile["question_count"] == 8
    assert profile["difficulty"] == "just_right"


def test_guided_frontend_replaces_learner_textbox_and_keeps_notes_ephemeral() -> None:
    html = Path("static/app.html").read_text(encoding="utf-8")
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")

    assert 'id="homework-profile"' not in html
    # Quick Start deliberately keeps a compact year selector alongside the
    # guided setup.
    assert 'id="homework-year"' in html
    assert 'id="homework-guide-question"' in html
    assert 'id="homework-quick-start"' in html
    assert "Plan today’s homework with me" in html
    assert "Learning notes are not saved in this browser" in html
    assert "Tell me about your learner" not in html

    function_body = javascript.split(
        "async function generateGuidedHomework()", 1
    )[1].split("async function generateQuickHomeworkEleven()", 1)[0]
    assert "setup_source: 'guided_homework'" in function_body
    assert "question_count: questionCount" in function_body
    assert "description:" not in function_body
    assert "target_school:" not in function_body

    save_choices_body = javascript.split(
        "function saveLearningChoices()", 1
    )[1].split("function restoreLearningChoices()", 1)[0]
    assert "homework-parent-notes" not in save_choices_body
    assert "homeworkPrompt:" not in save_choices_body


def test_subject_buttons_support_older_ipad_safari() -> None:
    html = Path("static/app.html").read_text(encoding="utf-8")
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")

    # Safari 12 cannot parse either operator, so one occurrence prevents the
    # entire app file from running and leaves dynamically rendered buttons blank.
    assert "?." not in javascript
    assert "??" not in javascript

    compatibility = javascript.index("installLegacySafariCompatibility")
    first_replace_children = javascript.index(".replaceChildren(")
    assert compatibility < first_replace_children
    assert "defineMethod(Element.prototype, 'replaceChildren'" in javascript
    assert "renderDefaultSubjectButtons();" in javascript
    assert javascript.index("renderDefaultSubjectButtons();") < javascript.index(
        "loadSubjects();"
    )

    # Change the URL whenever compatibility code changes so old Safari does not
    # reuse the previously broken script from its cache.
    assert "app.js?v=20260728-old-ipad-fix" in html
    assert "[hidden] { display: none !important; }" in html


def test_homework_generation_stops_shared_speech_without_reference_error() -> None:
    html = Path("static/app.html").read_text(encoding="utf-8")
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")

    helper = javascript.split("function stopSpeechPlayback()", 1)[1].split(
        "const HOMEWORK_COMMON_SUBJECTS", 1
    )[0]
    assert "window.HomeworkMagicSpeech.stop();" in helper
    assert javascript.index("function stopSpeechPlayback()") < javascript.index(
        "function showLoading()"
    )
    assert "revealLearningPanel(loading);" in javascript
    assert "revealLearningPanel(results);" in javascript
    assert 'id="loading" class="loading" role="status"' in html
    assert "make-homework-render-fix" in html


def test_quick_start_markup_keeps_results_in_the_main_container() -> None:
    html = Path("static/app.html").read_text(encoding="utf-8")

    assert html.count("<div") == html.count("</div>")
    assert html.count("<details") == html.count("</details>")
    assert 'onclick="generateGuidedHomework()"' in html
    assert 'onclick="generateHomework()"' in html
    assert 'onclick="generateCustomHomeworkEleven()"' in html
    assert 'onclick="changeElevenGuide()"' in html
