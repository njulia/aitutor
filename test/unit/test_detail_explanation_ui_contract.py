from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_explain_detail_keeps_quick_review_and_auto_reviews_first():
    js = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    assert "Never replace the Quick Review" in js
    assert "if (!reviewFeedback.trim())" in js
    assert "displayReview(quickData.review || '', reviewContext)" in js
    assert "container.appendChild(detailSection)" in js


def test_topic_mastery_has_per_question_detail_button_and_no_cache_message():
    html = (ROOT / "static/elevenplus-topic-mastery.html").read_text(encoding="utf-8")
    assert 'id="explain-button"' in html
    assert '/api/elevenplus/topic-mastery/explain' in html
    assert 'question_index: i' in html
    assert 'card.scrollIntoView' in html
    assert 'Saved explanation reused.' not in html


def test_topic_mastery_explanation_store_is_persistent_and_per_question(monkeypatch, tmp_path):
    import src.topic_mastery_explanations as store
    db_path = tmp_path / "topic_mastery.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    store.init_topic_mastery_explanations_db()
    store.save_explanation("doc-1", 0, "model-a", "Step by step")
    assert store.get_explanation("doc-1", 0, "model-a") == "Step by step"
    assert store.get_explanation("doc-1", 1, "model-a") is None
