from __future__ import annotations

import hashlib
import re
from pathlib import Path

from src import homework_rag
from src.cache import review_cache
from src.webapp import review_service


class _FirstWriteStore:
    embedding_dimension = 4

    def __init__(self):
        self.rows = {}

    def get_by_ids(self, ids):
        return [
            {
                "doc_id": method_id,
                "content": self.rows[method_id]["content"],
                "metadata": self.rows[method_id]["metadata"],
            }
            for method_id in ids
            if method_id in self.rows
        ]

    def add_documents_if_absent(self, texts, metadatas, ids, embeddings):
        for index, method_id in enumerate(ids):
            self.rows.setdefault(
                method_id,
                {
                    "content": texts[index],
                    "metadata": metadatas[index],
                    "embedding": embeddings[index],
                },
            )


def test_solution_method_store_preserves_first_method_without_question_or_learner_data(monkeypatch):
    store = _FirstWriteStore()
    monkeypatch.setattr(homework_rag, "_solution_method_store", store)

    question = "1. What is 6 × 7?"
    first_method = "Split 7 into 5 and 2, then add 30 and 12."
    first = homework_rag.save_solution_methods(
        [{"question": question, "method": first_method}], "Maths", 3
    )
    second = homework_rag.save_solution_methods(
        [{
            "question": "Question 1: What is 6 × 7?",
            "method": "A later attempt must not replace the first method.",
        }],
        "Maths",
        3,
    )

    method_id = homework_rag.solution_method_key(question, "Maths", 3)
    assert first[method_id] == first_method
    assert second[method_id] == first_method
    assert question not in method_id
    assert store.rows[method_id]["content"] == first_method
    assert "question" not in store.rows[method_id]["metadata"]
    assert "subject" not in store.rows[method_id]["metadata"]
    assert "student_id" not in store.rows[method_id]["metadata"]
    assert "student_answer" not in store.rows[method_id]["metadata"]
    assert store.rows[method_id]["embedding"] == [1.0, 0.0, 0.0, 0.0]


class _StructuredLLM:
    provider = "test"
    model = "test-model"

    def __init__(self):
        self.prompts = []

    def complete(self, messages, **_kwargs):
        prompt = "\n".join(str(item.get("content") or "") for item in messages)
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            return (
                '{"feedback_markdown":"## Check\\nThat answer needs another look.",'
                '"solution_methods":[{"id":"q1","method_markdown":'
                '"Count on in equal groups, then check the total."}]}'
            )
        return (
            '{"feedback_markdown":"## Check\\nThis new answer is correct.",'
            '"solution_methods":[]}'
        )


def test_second_attempt_reuses_method_without_sending_it_to_llm(monkeypatch):
    stored = {}

    def method_key(question, subject, year_group):
        normalised = re.sub(r"^\s*(?:question\s*)?\d+\s*[.):-]\s*", "", question, flags=re.I)
        raw = f"{subject.casefold()}|{year_group}|{' '.join(normalised.casefold().split())}"
        return "method_" + hashlib.sha256(raw.encode()).hexdigest()

    def load_methods(questions, subject, year_group):
        return {
            key: stored[key]
            for key in (method_key(question, subject, year_group) for question in questions)
            if key in stored
        }

    def save_methods(records, subject, year_group):
        for record in records:
            stored.setdefault(
                method_key(record["question"], subject, year_group),
                record["method"],
            )
        return load_methods(
            [record["question"] for record in records], subject, year_group
        )

    monkeypatch.setattr(homework_rag, "solution_method_key", method_key)
    monkeypatch.setattr(homework_rag, "load_solution_methods", load_methods)
    monkeypatch.setattr(homework_rag, "save_solution_methods", save_methods)
    review_cache.clear()

    llm = _StructuredLLM()
    question = "1. There are 4 bags with 3 apples in each. How many apples are there?"
    first = review_service.review_homework(
        question,
        "10",
        "Maths",
        {"year_group": 3},
        is_tutor_mode=True,
        llm_client=llm,
    )
    second = review_service.review_homework(
        question,
        "12",
        "Maths",
        {"year_group": 3},
        is_tutor_mode=True,
        llm_client=llm,
    )

    assert len(llm.prompts) == 2
    assert first["solution_methods"][0]["from_cache"] is False
    assert second["solution_methods"][0]["from_cache"] is True
    assert first["solution_methods"][0]["method"] == second["solution_methods"][0]["method"]
    assert "Count on in equal groups" not in llm.prompts[1]
    assert "No method is missing" in llm.prompts[1]
    assert "MISSING_METHODS:\n[]" in llm.prompts[1]
    assert "This new answer is correct" in second["llm_response"]
    assert "Count on in equal groups" in second["review"]


def test_rag_prompt_context_never_contains_saved_explanation_or_tip():
    context = review_service._rag_prompt_context(
        [{
            "question": "1. What is 6 × 7?",
            "student_answer": "42",
            "correct_answer": "42",
            "correct_letter": "",
            "explanation": "PRIVATE STORED METHOD",
            "tip": "PRIVATE STORED TIP",
            "is_correct": True,
        }]
    )
    prompt_context = "\n".join(context.values())
    assert "PRIVATE STORED METHOD" not in prompt_context
    assert "PRIVATE STORED TIP" not in prompt_context
    assert "Correct answer: 42" in prompt_context


def test_legacy_combined_review_does_not_send_saved_method_to_follow_up_llm():
    combined = (
        "## What to Improve\nCheck the multiplication fact.\n\n"
        "## A Helpful Way to Solve This Question\n"
        "PRIVATE SAVED METHOD"
    )

    cleaned = review_service._without_rendered_solution_methods(combined)

    assert "Check the multiplication fact" in cleaned
    assert "PRIVATE SAVED METHOD" not in cleaned


def test_browser_renders_methods_separately_and_excludes_them_from_follow_up_prompt():
    app_js = Path("static/js/app.js").read_text(encoding="utf-8")
    assert "data.llm_response || data.review" in app_js
    assert "data.solution_methods || []" in app_js
    assert "renderSolutionMethods(solutionMethods)" in app_js
    assert "#review-result .teacher-feedback-output" in app_js
