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

