import sys
import types

import pytest

from src.webapp import review_service


class MemoryCache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value


class FakeLLM:
    def __init__(self, response="Friendly feedback"):
        self.response = response
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return self.response


@pytest.fixture
def service_dependencies(monkeypatch):
    review_cache = MemoryCache()

    llm_client_module = types.ModuleType("src.llm_client")
    llm_client_module.format_prompt = lambda template, **kwargs: kwargs
    llm_client_module.build_messages = lambda prompt: prompt

    prompts_module = types.ModuleType("src.prompts")
    prompts_module.REVIEW_HOMEWORK_PROMPT = "homework prompt"
    prompts_module.REVIEW_TUTOR_QUESTION_PROMPT = "tutor prompt"

    cache_module = types.ModuleType("src.cache")
    cache_module.review_cache = review_cache
    cache_module.make_cache_key = lambda *parts: "|".join(str(p) for p in parts)

    math_tools_module = types.ModuleType("src.tools.math_tools")
    math_tools_module.verify_math_answer = (
        lambda question, student, correct: {
            "is_correct": student.strip().lower() == correct.strip().lower()
        }
    )

    tools_package = types.ModuleType("src.tools")
    tools_package.__path__ = []

    monkeypatch.setitem(sys.modules, "src.llm_client", llm_client_module)
    monkeypatch.setitem(sys.modules, "src.prompts", prompts_module)
    monkeypatch.setitem(sys.modules, "src.cache", cache_module)
    monkeypatch.setitem(sys.modules, "src.tools", tools_package)
    monkeypatch.setitem(sys.modules, "src.tools.math_tools", math_tools_module)

    return review_cache


def install_rag(monkeypatch, answers):
    rag_module = types.ModuleType("src.homework_rag")
    rag_module.search_homework_answers = lambda doc_id: answers
    monkeypatch.setitem(sys.modules, "src.homework_rag", rag_module)


def test_tutor_review_selects_dict_answer_by_question_index(monkeypatch, service_dependencies):
    install_rag(monkeypatch, [
        {"question": "1. 1 + 2 = ?", "answer": "3"},
        {"question": "2. 10 - 4 = ?", "answer": "6"},
    ])
    llm = FakeLLM()

    result = review_service.review_homework(
        homework_content="10 - 4 = ?",
        student_answers="6",
        subject="Maths",
        profile={"year_group": 3},
        is_tutor_mode=True,
        homework_doc_id="doc-1",
        question_index=1,
        llm_client=llm,
    )

    assert result["success"] is True
    assert result["from_rag_answers"] is True
    assert "2. 10 - 4 = ?" in result["review"]
    assert "| 6 | 6 |" in result["review"]
    assert llm.messages["correct_answers_section"].find('"answer": "6"') >= 0
    assert llm.messages["correct_answers_section"].find('"answer": "3"') == -1


def test_tutor_review_selects_string_answer_by_question_index(monkeypatch, service_dependencies):
    install_rag(monkeypatch, ["3", "6"])
    llm = FakeLLM()

    result = review_service.review_homework(
        homework_content="10 - 4 = ?",
        student_answers="6",
        subject="Maths",
        profile={"year_group": 3},
        is_tutor_mode=True,
        homework_doc_id="doc-1",
        question_index=1,
        llm_client=llm,
    )

    assert result["success"] is True
    assert result["from_rag_answers"] is True
    assert "10 - 4 = ?" in result["review"]
    assert "| 6 | 6 |" in result["review"]


def test_old_client_falls_back_to_normalized_text_match(monkeypatch, service_dependencies):
    install_rag(monkeypatch, [
        {"question": "1. 1 + 2 = ?", "answer": "3"},
        {"question": "2. 10 - 4 = ?", "answer": "6"},
    ])

    result = review_service.review_homework(
        homework_content="10 - 4 = ?",
        student_answers="6",
        subject="Maths",
        profile={"year_group": 3},
        is_tutor_mode=True,
        homework_doc_id="doc-1",
        question_index=None,
        llm_client=FakeLLM(),
    )

    assert result["success"] is True
    assert "2. 10 - 4 = ?" in result["review"]


def test_out_of_range_index_does_not_use_wrong_rag_answer(monkeypatch, service_dependencies):
    install_rag(monkeypatch, [
        {"question": "1. Different question", "answer": "wrong"},
    ])
    llm = FakeLLM("LLM fallback feedback")

    result = review_service.review_homework(
        homework_content="10 - 4 = ?",
        student_answers="6",
        subject="Maths",
        profile={"year_group": 3},
        is_tutor_mode=True,
        homework_doc_id="doc-1",
        question_index=9,
        llm_client=llm,
    )

    assert result["success"] is True
    assert result["from_rag_answers"] is False
    assert result["review"] == "LLM fallback feedback"
