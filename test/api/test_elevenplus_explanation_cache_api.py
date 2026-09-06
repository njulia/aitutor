"""Cache-first API coverage for 11+ detailed explanations."""
from __future__ import annotations

import uuid

import pytest


pytestmark = pytest.mark.api


class _RecordingLLM:
    provider = "api"
    model = "test-detail-model"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, _messages, **_kwargs) -> str:
        self.calls += 1
        return (
            "## How to solve it\nUse the clues one small step at a time.\n\n"
            "## Why it works\nEach step checks the rule in the question.\n\n"
            "## Helpful tip\nCheck your working before choosing."
        )


async def _identity(_request):
    return "explanation-cache-child", "parent@example.com", None


async def _registered(*_args, **_kwargs):
    return None


def _allow_11plus_explanations(app_module, monkeypatch, llm: _RecordingLLM) -> None:
    monkeypatch.setattr(app_module, "_resolve_request_identity", _identity)
    monkeypatch.setattr(app_module, "_require_registered_identity", _registered)
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *_args, **_kwargs: True)
    app_module.llm = llm


def test_topic_mastery_detail_explanation_is_saved_and_reused(client, app_module, monkeypatch) -> None:
    llm = _RecordingLLM()
    _allow_11plus_explanations(app_module, monkeypatch, llm)
    request = {
        "subject": "Maths",
        "topic_index": 1,
        "mastery_level": 1,
        "doc_id": "cache-topic-" + uuid.uuid4().hex,
        "question_index": 0,
        "question": "What is one half of 18?",
        "topic": "Fractions",
    }

    first = client.post("/api/elevenplus/topic-mastery/explain", json=request)
    second = client.post("/api/elevenplus/topic-mastery/explain", json=request)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["saved"] is True
    assert second.json()["from_saved"] is True
    assert second.json()["explanation"] == first.json()["explanation"]
    assert llm.calls == 1


def test_year_round_detail_explanation_is_saved_and_reused(client, app_module, monkeypatch) -> None:
    llm = _RecordingLLM()
    _allow_11plus_explanations(app_module, monkeypatch, llm)
    request = {
        "subject": "English",
        "doc_id": "cache-year-" + uuid.uuid4().hex,
        "question_index": 0,
        "question": "Which word best matches the meaning of tiny?",
        "topic": "Vocabulary",
        "plan_week": 1,
    }

    first = client.post("/api/elevenplus/year-round/explain", json=request)
    second = client.post("/api/elevenplus/year-round/explain", json=request)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["saved"] is True
    assert second.json()["from_saved"] is True
    assert second.json()["explanation"] == first.json()["explanation"]
    assert llm.calls == 1
