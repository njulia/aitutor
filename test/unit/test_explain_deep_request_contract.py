from pathlib import Path

def test_explain_deep_sends_tutor_question_index():
    source = Path("static/js/app.js").read_text(encoding="utf-8")
    body = source.split("fetch('/api/explain-deep'", 1)[1].split("catch (error)", 1)[0]
    assert "question_index: Number.isInteger(reviewContext.question_index)" in body
