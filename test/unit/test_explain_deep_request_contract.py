from pathlib import Path


def test_explain_deep_requests_all_questions_from_main_button():
    root = Path(__file__).resolve().parents[2]
    source = (root / "static/js/app.js").read_text(encoding="utf-8")
    body = source.split("async function ExplainDeep()", 1)[1].split("function displayExplainDeep", 1)[0]
    assert "question_index: null" in body
    assert "Making step-by-step explanations for all your questions" in body
