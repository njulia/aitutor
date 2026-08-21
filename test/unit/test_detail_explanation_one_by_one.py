from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_explain_in_detail_requests_the_whole_homework_set():
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    start = script.index("async function ExplainDeep()")
    end = script.index("function displayExplainDeep", start)
    explain = script[start:end]
    assert "Making step-by-step explanations for all your questions" in explain
    assert "question_index: null" in explain
    assert "displayExplainDeep(explanation)" in explain


def test_detail_explanation_can_still_target_one_question_for_legacy_tutor_calls():
    service = (ROOT / "src/webapp/review_service.py").read_text(encoding="utf-8")
    assert "question_index is not None" in service
    assert "_select_detail_question(" in service


def test_detail_explanation_is_persisted_per_question():
    service = (ROOT / "src/webapp/review_service.py").read_text(encoding="utf-8")
    rag = (ROOT / "src/homework_rag.py").read_text(encoding="utf-8")
    assert "detail_explanation_key(" in service
    assert "save_detail_explanation(" in service
    assert "load_detail_explanation(" in service
    assert '"kind": "detail_explanation"' in rag
    assert "add_documents_if_absent" in rag


def test_all_question_prompt_requires_every_question():
    prompts = (ROOT / "src/prompts.py").read_text(encoding="utf-8")
    start = prompts.index("EXPLAIN_ALL_QUESTIONS_PROMPT =")
    prompt = prompts[start:]
    assert "EVERY question" in prompt
    assert "## Question N" in prompt
    assert "{question}" in prompt
