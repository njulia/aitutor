from src.webapp import explanation_store
from src.webapp import review_service


class RecordingLLM:
    provider = "deepseek"
    model = "deepseek-v4-flash"

    def __init__(self):
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        return "## How to solve it\nThink about the clues in the question one step at a time.\n\n**Remember:** check each step."


def test_explain_deep_is_question_by_question_and_reuses_shared_explanations(monkeypatch):
    stored = {}

    def fake_get(key):
        return stored.get(key)

    def fake_save(key, **kwargs):
        value = {"question_hash": key, **kwargs}
        stored[key] = value
        return value

    monkeypatch.setattr(explanation_store, "get_explanation", fake_get)
    monkeypatch.setattr(explanation_store, "save_explanation", fake_save)

    llm = RecordingLLM()
    homework = """Maths Homework - Year 3 - Addition

1. What is 2 + 2?

2. What is 5 + 3?"""

    first = review_service.explain_deep(
        homework,
        "4\n999",  # must not be sent to the LLM
        "Maths",
        {"year_group": 3},
        llm_client=llm,
    )

    assert first["success"] is True
    assert first["created_count"] == 2
    assert first["cached_count"] == 0
    assert len(llm.calls) == 2
    prompt_text = "\n".join(message.get("content", "") for message in llm.calls[0])
    assert "999" not in prompt_text
    assert "Correct answer" in prompt_text

    second = review_service.explain_deep(
        homework,
        "1\n1",
        "Maths",
        {"year_group": 3},
        llm_client=llm,
    )

    assert second["success"] is True
    assert second["created_count"] == 0
    assert second["cached_count"] == 2
    assert len(llm.calls) == 2
    assert all("student_answer" not in item for item in second["explanations"])
    assert all("correct_answer" not in item for item in second["explanations"])
