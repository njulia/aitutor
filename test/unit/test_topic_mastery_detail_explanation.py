from __future__ import annotations

from pathlib import Path


def test_topic_mastery_detail_endpoint_and_persistent_store_are_present():
    root = Path(__file__).resolve().parents[2]
    web = (root / "web_app.py").read_text(encoding="utf-8")
    html = (root / "static/elevenplus-topic-mastery.html").read_text(encoding="utf-8")
    store = (root / "src/webapp/topic_mastery_explanation_store.py").read_text(encoding="utf-8")

    assert '@app.post("/api/elevenplus/topic-mastery/explain")' in web
    assert "question_index" in web
    assert "save_topic_mastery_explanation" in web
    assert "get_topic_mastery_explanation" in web
    assert "Explain in detail" in html
    assert "/api/elevenplus/topic-mastery/explain" in html
    assert "question_key" in store
    assert "student_answer" not in store.lower()
    assert "answers" not in store.lower()


def test_topic_mastery_explanation_request_does_not_accept_student_answer():
    root = Path(__file__).resolve().parents[2]
    web = (root / "web_app.py").read_text(encoding="utf-8")
    start = web.index("class TopicMasteryExplainRequest")
    end = web.index("class ReviewRequest", start)
    block = web[start:end]
    assert "answers" not in block
    assert "student_answer" not in block
