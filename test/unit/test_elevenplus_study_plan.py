from __future__ import annotations

import pytest

from src import elevenplus_study_plan as plans


pytestmark = pytest.mark.unit


def _result():
    return {
        "exam": {"id": "common-full-1", "title": "Mock"},
        "score": {"correct": 4, "total": 8, "percent": 50},
        "subject_breakdown": [{"subject": "Maths", "correct": 4, "total": 8, "percent": 50}],
        "questions": [
            {"correct": False, "subject": "Maths", "topic": "Fractions"},
            {"correct": False, "subject": "Maths", "topic": "Fractions"},
            {"correct": False, "subject": "English", "topic": "Vocabulary"},
        ],
    }


def _questions(subject, topic, count=10):
    return [
        {
            "number": i + 1,
            "question": f"{subject} {topic} question {i + 1}",
            "options": ["A", "B", "C", "D"],
            "subject": subject,
            "topic": topic,
            "doc_id": f"doc-{subject}-{topic}",
        }
        for i in range(count)
    ]


def test_study_plan_prefers_rag_and_does_not_call_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(plans, "_rag_questions", lambda subject, topic, year: _questions(subject, topic))
    monkeypatch.setattr(plans, "_generate_missing", lambda *args: calls.append(args) or [])
    saved = {}
    monkeypatch.setattr(plans, "save_mock_study_plan", lambda student_id, plan: saved.update(plan=plan))

    plan = plans.generate_mock_study_plan(student_id="s1", year_group=5, exam_result=_result())

    assert len(plan["days"]) == 30
    assert all(day["minutes"] == 30 and len(day["questions"]) == 5 for day in plan["days"])
    assert calls == []
    assert saved["plan"] is plan
    assert all(source.startswith("RAG:") for source in plan["sources"])


def test_study_plan_generates_only_on_rag_miss_and_saves_back(monkeypatch):
    generated = _questions("Maths", "Fractions", 10)
    generated.append({
        "number": 11,
        "question": "Generated extra",
        "options": ["A", "B", "C", "D"],
        "correct_letter": "A",
        "answer": "A",
        "explanation": "Because A is correct.",
        "subject": "Maths",
        "topic": "Fractions",
    })
    generated = [dict(q, correct_letter="A", answer="A", explanation="Short explanation") for q in generated]

    calls = []
    monkeypatch.setattr(plans, "_rag_questions", lambda subject, topic, year: [])
    monkeypatch.setattr(plans, "_generate_missing", lambda *args: calls.append(args) or generated)
    monkeypatch.setattr(plans, "_store_generated", lambda subject, topic, year, questions: "generated-doc")
    monkeypatch.setattr(plans, "save_mock_study_plan", lambda student_id, plan: None)

    plan = plans.generate_mock_study_plan(student_id="s1", year_group=5, exam_result=_result())

    assert calls
    assert all(source.startswith("LLM→RAG:") for source in plan["sources"])
    assert "Maths: Fractions" in plan["generated_topics"]
    assert len(plan["days"]) == 30
