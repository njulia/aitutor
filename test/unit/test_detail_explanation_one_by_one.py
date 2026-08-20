from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start)
    return source[start:end]


def test_detail_explanation_is_requested_one_question_at_a_time():
    script = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    explain = _function(script, "async function ExplainDeep()", "function ensureExplainDeepSection")
    assert "while (nextIndex < (totalQuestions || Infinity))" in explain
    assert "question_index: Number.isInteger(reviewContext.question_index)" in explain
    assert "answers: ''" in explain
    assert "appendExplainDeepItem(data);" in explain


def test_detail_explanation_is_persisted_per_question():
    service = (ROOT / "src/webapp/review_service.py").read_text(encoding="utf-8")
    rag = (ROOT / "src/homework_rag.py").read_text(encoding="utf-8")
    assert "detail_explanation_key(" in service
    assert "save_detail_explanation(" in service
    assert "load_detail_explanation(" in service
    assert '"kind": "detail_explanation"' in rag
    assert "add_documents_if_absent" in rag


def test_detail_prompt_does_not_use_student_answer():
    prompts = (ROOT / "src/prompts.py").read_text(encoding="utf-8")
    start = prompts.index("EXPLAIN_SINGLE_QUESTION_PROMPT =")
    end = prompts.index("EXPLAIN_DEEP_PROMPT =", start)
    prompt = prompts[start:end]
    assert "{student_answer}" not in prompt
    assert "{question}" in prompt
    assert "{trusted_answer}" in prompt
