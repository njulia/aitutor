from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def test_review_feedback_is_rendered_after_the_unchanged_questions() -> None:
    page = (ROOT / "static/app.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    assert page.index('id="homework-results"') < page.index('id="review-result"')
    review_loading = _function(script, "showReviewLoading", "hideLoading")
    assert "results.style.display = 'block'" in review_loading
    assert "results.style.display = 'none'" not in review_loading
    assert "data-review-pending" in review_loading
    assert "lockSubmittedWorkForReview()" in review_loading

    display_review = _function(script, "displayReview", "ExplainDeep")
    assert "document.getElementById('review-result')" in display_review
    assert "homework-results" not in display_review


def test_every_answer_check_uses_the_non_destructive_review_loader() -> None:
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    review_current = _function(script, "reviewCurrentQuestion", "nextQuestion")
    review_generated = _function(
        script, "reviewGeneratedHomework", "inferUploadedHomeworkSubject"
    )
    review_uploaded = _function(
        script, "reviewHomeworkWithContent", "buildGeneratedReviewContext"
    )
    practice_review = _function(script, "checkPracticeAnswers", "exitPracticeMode")

    for review_flow in (
        review_current,
        review_generated,
        review_uploaded,
        practice_review,
    ):
        assert "showReviewLoading(" in review_flow
        assert "showLoading();" not in review_flow


def test_review_pending_state_keeps_answers_readable() -> None:
    stylesheet = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    assert '.hm-app .review-pending' in stylesheet
    assert '#results[aria-busy="true"] .answer-input-inline[readonly]' in stylesheet
    assert "unlockSubmittedWorkAfterReview()" in script


def test_explain_in_detail_keeps_questions_and_answers_visible() -> None:
    page = (ROOT / "static/app.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    explain_deep = _function(script, "ExplainDeep", "ensureExplainDeepSection")
    detailed_result = _function(script, "ensureExplainDeepSection", "backToReview")
    review_loading = _function(script, "showReviewLoading", "hideLoading")

    assert "showReviewLoading('Explaining question 1…'" in explain_deep
    assert "question_index: Number.isInteger(reviewContext.question_index)" in explain_deep
    assert "while (nextIndex < (totalQuestions || Infinity))" in explain_deep
    assert "preserveExisting: true" in explain_deep
    assert "showLoading();" not in explain_deep
    assert "insertAdjacentHTML('beforeend', pendingMarkup)" in review_loading
    assert "document.getElementById('review-result')" in detailed_result
    assert "homework-results" not in detailed_result
    assert page.index('id="homework-results"') < page.index('id="review-result"')
    assert "detail-review-stable" in page


def test_independent_homework_review_removes_generated_questions_and_feedback() -> None:
    page = (ROOT / "static/app.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    prepare_review = _function(
        script, "prepareIndependentHomeworkReviewDisplay", "reviewHomework"
    )
    review_uploaded = _function(
        script, "reviewHomeworkWithContent", "buildGeneratedReviewContext"
    )
    show_results = _function(script, "showResults", "clearResults")

    assert "currentHomework = [];" in prepare_review
    assert "activeReviewContext = null;" in prepare_review
    assert "clearSavedState();" in prepare_review
    assert "homeworkResults.replaceChildren();" in prepare_review
    assert "homeworkResults.hidden = true;" in prepare_review
    assert "reviewContainer.replaceChildren();" in prepare_review
    assert "INDEPENDENT_REVIEW_ACTION_BUTTONS_HTML" in prepare_review

    assert "prepareIndependentHomeworkReviewDisplay();" in review_uploaded
    assert "requestBody.is_eleven_plus = false;" in review_uploaded
    assert "currentHomework.some" not in review_uploaded
    assert "currentHomework[0]" not in review_uploaded

    # A newly generated Make Homework or 11+ Practice quest restores its own
    # question area, so this isolation does not alter those two flows.
    assert "homeworkResults.hidden = false;" in show_results
    assert 'id="results-heading"' in page
    assert "uploaded-review-isolation" in page


def test_uploaded_review_extra_practice_returns_to_uploaded_feedback() -> None:
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    improve = _function(script, "ImprovePractice", "showPracticeGenerationMessage")
    display_practice = _function(
        script, "displayPracticeQuestions", "checkPracticeAnswers"
    )
    exit_practice = _function(script, "exitPracticeMode", "TrackProgress")

    assert "reviewContext.review_source === 'independent'" in improve
    assert "container.hidden = false;" in display_practice
    assert "Back to Feedback" in display_practice
    assert "returnToIndependentReview" in exit_practice
    assert "homeworkResults.hidden = true;" in exit_practice
    assert "restoreSavedState();" in exit_practice
    assert "INDEPENDENT_REVIEW_ACTION_BUTTONS_HTML" in exit_practice
