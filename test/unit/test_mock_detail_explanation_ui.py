from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_mock_question_detail_explanations_use_topic_mastery_two_column_layout() -> None:
    script = (ROOT / "static/js/mock-exams.js").read_text(encoding="utf-8")
    css = (ROOT / "static/css/mock-exams.css").read_text(encoding="utf-8")

    assert "function splitDetailedExplanationParts(explanation)" in script
    assert "How to solve it" in script
    assert "💡 Why it works" in script
    assert "⭐ Helpful tip" in script
    assert "mock-detailed-explanation-layout" in script
    assert "mock-detailed-explanation-aside" in script
    assert "mock-detailed-explanation-layout {\n  display: grid;\n  grid-template-columns:" in css
    assert ".mock-detailed-explanation-callout.why" in css
    assert ".mock-detailed-explanation-callout.tip" in css


def test_mock_detail_explanation_has_a_safe_retry_after_a_temporary_failure() -> None:
    script = (ROOT / "static/js/mock-exams.js").read_text(encoding="utf-8")

    assert "mock-detailed-explanation-retry" in script
    assert "retry.addEventListener('click', load);" in script
    assert "target.replaceChildren(createExplanationLoadingCard());" in script
