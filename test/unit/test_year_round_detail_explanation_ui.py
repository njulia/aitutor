from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_year_round_detail_explanation_uses_the_topic_mastery_three_part_layout() -> None:
    html = (ROOT / "static/elevenplus-year-round-plan.html").read_text(encoding="utf-8")

    assert "function splitYearDetailExplanationParts(explanation)" in html
    assert "function renderYearRoundDetailExplanation(label, questionText, explanation)" in html
    assert "How to solve it" in html
    assert "💡 Why it works" in html
    assert "⭐ Helpful tip" in html
    assert "year-detail-layout { display: grid; grid-template-columns:" in html
    assert "year-detail-callout why" in html
    assert "year-detail-callout tip" in html
