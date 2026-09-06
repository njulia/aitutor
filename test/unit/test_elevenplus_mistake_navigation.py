"""Regression coverage for the app-page mistake-practice destination."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_app_mistake_buttons_keep_the_active_11plus_journey() -> None:
    source = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

    generated_buttons = _section(
        source, "const HOMEWORK_ACTION_BUTTONS_HTML", "const INDEPENDENT_REVIEW_ACTION_BUTTONS_HTML"
    )
    independent_buttons = _section(
        source, "const INDEPENDENT_REVIEW_ACTION_BUTTONS_HTML", "function resetHomeworkActionButtons"
    )
    practice_mistakes = _section(source, "function practiceMistakes()", "// ---- Admin Tools Functions")
    independent_review = _section(
        source, "function prepareIndependentHomeworkReviewDisplay()", "async function reviewHomework()"
    )

    # Both button templates are redrawn during a session, so neither may lock
    # a child into the normal-homework mistake page.
    assert 'onclick="practiceMistakes()"' in generated_buttons
    assert 'onclick="practiceMistakes()"' in independent_buttons
    assert "window.location.href='/homework-mistakes'" not in generated_buttons
    assert "window.location.href='/homework-mistakes'" not in independent_buttons

    # The route uses the current question set and preserved review context.
    assert "activeReviewContext && activeReviewContext.is_eleven_plus" in practice_mistakes
    assert "? '/elevenplus-mistakes' : '/homework-mistakes'" in practice_mistakes

    # A pasted/uploaded primary-homework review starts a new journey, so it
    # cannot inherit the route from a prior 11+ extra-practice session.
    assert "currentPracticeIsElevenPlus = false;" in independent_review
    assert "currentPracticeTopic = '';" in independent_review
