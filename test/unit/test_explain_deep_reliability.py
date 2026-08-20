from __future__ import annotations

from pathlib import Path
import uuid

from src.webapp import review_service


class EmptyLLM:
    provider = "api"
    model = "empty-model"

    def complete(self, *_args, **_kwargs):
        return ""


def _stub_rag(monkeypatch):
    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_args: [
            {
                "question": "1. What is 2 + 2?",
                "answer": "4",
                "explanation": "Add 2 and 2 to make 4.",
                "tip": "Count on two more from 2.",
            },
            {
                "question": "2. What is 5 - 2?",
                "answer": "3",
                "explanation": "Take 2 away from 5 to get 3.",
                "tip": "Count backwards two steps.",
            },
        ],
    )


def test_explain_deep_empty_llm_returns_trusted_rag_fallback(monkeypatch):
    _stub_rag(monkeypatch)
    result = review_service.explain_deep(
        "1. What is 2 + 2?\n2. What is 5 - 2?",
        "1. 4\n2. 4",
        "Maths",
        {"year_group": 2, "age": 6},
        homework_doc_id=f"explain-fallback-{uuid.uuid4().hex}",
        llm_client=EmptyLLM(),
    )

    assert result["success"] is True
    assert result["llm_fallback"] is True
    assert result["model_used"] is None
    assert result["explanation"]
    assert "## How to solve it" in result["explanation"]
    assert "Take 2 away from 5 to get 3." not in result["explanation"]


def test_explain_deep_keeps_existing_feedback_when_non_rag_model_is_empty():
    result = review_service.explain_deep(
        "What is 3 + 4?",
        "7",
        "Maths",
        {"year_group": 2, "age": 6},
        review_feedback="## Teacher Feedback\n\nYour answer is correct.",
        llm_client=EmptyLLM(),
    )

    assert result["success"] is True
    assert result["llm_fallback"] is True
    assert "Your answer is correct." not in result["explanation"]
    assert "How to solve it" in result["explanation"]
    assert "## Helpful tip" in result["explanation"]


def test_app_study_plan_tab_does_not_poll_every_15_seconds():
    source = (Path(__file__).resolve().parents[2] / "static/app.html").read_text(
        encoding="utf-8"
    )
    start = source.index("const tab = document.getElementById('mock-study-plan-tab')")
    end = source.index("</script>", start)
    block = source[start:end]

    assert "refreshMockStudyPlanTab();" in block
    assert "window.setInterval(refreshMockStudyPlanTab, 15000)" not in block
