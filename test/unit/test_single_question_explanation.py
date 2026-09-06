from src.webapp import explanation_store
from src.webapp import review_service


class RecordingLLM:
    provider = "deepseek"
    model = "deepseek-v4-flash"

    def __init__(self):
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        return (
            "## Question 1\n\n"
            "## How to solve it\nThink about the clues in the question one step at a time.\n\n"
            "## Why it works\nSmall steps make the method easier to check.\n\n"
            "## Helpful tip\nCheck each step before you choose an answer.\n\n"
            "## Question 2\n\n"
            "## How to solve it\nUse the information in the question one step at a time.\n\n"
            "## Why it works\nEach step follows from the one before it.\n\n"
            "## Helpful tip\nRead the question again when you finish."
        )


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
    # Missing questions are generated together, so the first open makes one
    # request rather than one slow request per question.
    assert len(llm.calls) == 1
    prompt_text = "\n".join(message.get("content", "") for message in llm.calls[0])
    assert "999" not in prompt_text
    assert "Trusted answer" in prompt_text

    # Simulate a fresh worker with no in-process cache. The durable shared
    # explanation should still load without another model request.
    from src.cache import explain_cache
    explain_cache.clear()

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
    assert len(llm.calls) == 1
    # Shared explanations never echo this child's later answers.
    assert "Your answer:" not in second["explanation"]
    assert "student_answer" not in second["explanation"]
