from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_topic_mastery_catalogue_and_page_are_available(client) -> None:
    page = client.get("/elevenplus-topic-mastery")
    assert page.status_code == 200
    assert "11+ Topic Mastery" in page.text

    response = client.get("/api/elevenplus/topic-mastery/catalog")
    assert response.status_code == 200
    data = response.json()
    assert len(data["subjects"]) == 4
    assert all(len(subject["topics"]) == 11 for subject in data["subjects"])
    assert len(data["levels"]) == 5


def test_topic_mastery_fetch_uses_exact_isolated_metadata(client, monkeypatch) -> None:
    import src.elevenplus_rag as rag

    captured = {}

    def fake_search(year_group, subject, **kwargs):
        captured.update({"year_group": year_group, "subject": subject, **kwargs})
        return [{"doc_id": "maths_mastery_08", "content": "private source", "metadata": {}}]

    questions = [{
        "number": 1,
        "question": "Which fraction is one half?",
        "options": [{"label": "A", "text": "1/3"}, {"label": "B", "text": "1/2"}],
    }]
    monkeypatch.setattr(rag, "search_homework_by_metadata", fake_search)
    monkeypatch.setattr(rag, "get_homework_questions", lambda *_: questions)

    response = client.post(
        "/api/elevenplus/topic-mastery/practice",
        json={"subject": "Maths", "topic_index": 2, "mastery_level": 3},
    )
    assert response.status_code == 200, response.text
    assert captured == {
        "year_group": 6,
        "subject": "Maths-topic-mastery",
        "k": 1,
        "content_type": "topic_mastery",
        "mastery_set_index": 8,
    }
    item = response.json()["homework"][0]
    assert item["mastery_set_index"] == 8
    assert item["content_type"] == "topic_mastery"
    assert item["questions"] == questions
    assert "private source" not in item["content"]


def test_ordinary_generate_api_rejects_internal_mastery_subject(client) -> None:
    response = client.post(
        "/api/generate",
        json={
            "profile": {"year_group": 6, "age": 11},
            "subjects": ["Maths-topic-mastery"],
            "is_eleven_plus": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["policy_blocked"] is True

