"""Tests for request-local routing across DeepSeek and Vertex AI."""
from __future__ import annotations

from src import llm_client


def _configured_client(monkeypatch):
    monkeypatch.setenv("QUICK_REVIEW_PROVIDER", "deepseek")
    monkeypatch.setenv("DETAIL_REVIEW_PROVIDER", "vertex_ai")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "homework-magic-prod")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west2")
    monkeypatch.setattr(llm_client, "DEEPSEEK_API_KEY", "test-deepseek-key")
    return llm_client.LLMClient(
        provider="deepseek",
        model=llm_client.QUICK_REVIEW_MODEL,
    )


def test_model_tiers_resolve_to_separate_providers(monkeypatch) -> None:
    client = _configured_client(monkeypatch)

    assert client.provider_for_model(llm_client.QUICK_REVIEW_MODEL) == "deepseek"
    assert client.provider_for_model(llm_client.DETAIL_REVIEW_MODEL) == "vertex_ai"


def test_detail_client_uses_vertex_project_and_region(monkeypatch) -> None:
    client = _configured_client(monkeypatch)

    detail_client = client.with_model(llm_client.DETAIL_REVIEW_MODEL)

    assert detail_client.provider == "vertex_ai"
    assert detail_client.model == "gemini-2.5-flash"
    assert detail_client.vertex_project == "homework-magic-prod"
    assert detail_client.vertex_location == "europe-west2"
    assert detail_client.api_base is None
    assert detail_client.api_key is None


def test_quick_client_uses_deepseek_endpoint(monkeypatch) -> None:
    client = _configured_client(monkeypatch)

    quick_client = client.with_model(llm_client.QUICK_REVIEW_MODEL)

    assert quick_client.provider == "deepseek"
    assert quick_client.api_base == "https://api.deepseek.com/"


def test_vertex_message_conversion_separates_system_instruction() -> None:
    contents, system_instruction = llm_client.LLMClient._vertex_contents([
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Explain fractions."},
        {"role": "assistant", "content": "Start with halves."},
    ])

    assert system_instruction == "Be helpful."
    assert contents == [
        {"role": "user", "parts": [{"text": "Explain fractions."}]},
        {"role": "model", "parts": [{"text": "Start with halves."}]},
    ]
