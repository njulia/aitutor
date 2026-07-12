from pathlib import Path

from src.webapp.memory_store import LearningMemoryStore, infer_topic


def store(tmp_path: Path) -> LearningMemoryStore:
    return LearningMemoryStore(f"sqlite+pysqlite:///{tmp_path / 'memory.db'}")


def test_memory_is_off_by_default_and_does_not_record(tmp_path):
    memory = store(tmp_path)
    settings = memory.get_settings("stu_1", "acct_1")
    assert settings["enabled"] is False
    assert memory.record_event(
        student_id="stu_1", account_id="acct_1", subject="Maths", topic="Fractions", outcome=0.5
    ) is False
    assert memory.summary("stu_1", "acct_1")["recent_events"] == []


def test_enabled_memory_updates_mastery_without_raw_text(tmp_path):
    memory = store(tmp_path)
    memory.update_settings("stu_1", "acct_1", enabled=True, retention_days=90)
    assert memory.record_event(
        student_id="stu_1",
        account_id="acct_1",
        subject="Maths",
        topic="Fractions",
        outcome=0.5,
        attempted=4,
        correct_count=2,
        misconception_code="fraction_denominator_confusion",
        metadata={"mode": "tutor", "raw_answer": "must not be stored"},
    )
    data = memory.summary("stu_1", "acct_1")
    assert data["all_topics"][0]["topic"] == "Fractions"
    assert data["all_topics"][0]["mastery_score"] == 0.5
    event = data["recent_events"][0]
    assert "raw_answer" not in event
    assert "question" not in event


def test_parent_can_delete_topic_and_all_memory(tmp_path):
    memory = store(tmp_path)
    memory.update_settings("stu_1", "acct_1", enabled=True)
    for topic in ("Fractions", "Decimals"):
        memory.record_event(
            student_id="stu_1", account_id="acct_1", subject="Maths", topic=topic, outcome=0.75
        )
    assert memory.delete_topic("stu_1", "acct_1", "Maths", "Fractions") == 1
    assert [item["topic"] for item in memory.summary("stu_1", "acct_1")["all_topics"]] == ["Decimals"]
    assert memory.delete_all("stu_1", "acct_1") == 1
    assert memory.summary("stu_1", "acct_1")["all_topics"] == []


def test_prompt_context_is_small_and_educational(tmp_path):
    memory = store(tmp_path)
    memory.update_settings("stu_1", "acct_1", enabled=True)
    memory.update_preferences(
        "stu_1", "acct_1", explanation_style="worked_example", hint_style="small_hint"
    )
    memory.record_event(
        student_id="stu_1", account_id="acct_1", subject="Maths", topic="Fractions", outcome=0.25
    )
    context = memory.prompt_context("stu_1", "acct_1", max_chars=300)
    assert "Fractions" in context
    assert "worked_example" in context
    assert len(context) <= 300


def test_topic_inference_is_deterministic():
    assert infer_topic("Maths", "Add two fractions with the same denominator") == "Fractions"
    assert infer_topic("English", "Read the passage and answer the comprehension questions") == "Reading comprehension"
