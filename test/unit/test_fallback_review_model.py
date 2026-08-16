from pathlib import Path

import pytest

from src.webapp import review_service

pytestmark = pytest.mark.unit


class RoutedLLM:
    provider = "api"
    model = "test-model"

    def complete(self, _messages, **kwargs):
        model = kwargs.get("model")
        if model == "detail-test-model":
            return ""
        if model == "quick-test-model":
            return ""
        return """## Similar Practice Questions
1. What is 8 + 5?
2. What is 9 + 6?
3. What is 7 + 8?

## Quick Revision Notes
Add the ones first, then the tens.
"""


def test_empty_detail_and_quick_models_use_dedicated_fallback(monkeypatch):
    monkeypatch.setattr(review_service, "DETAIL_REVIEW_MODEL", "detail-test-model")
    monkeypatch.setattr(review_service, "QUICK_REVIEW_MODEL", "quick-test-model")
    monkeypatch.setattr(review_service, "FALLBACK_REVIEW_MODEL", "fallback-test-model")

    result = review_service.improve_practice(
        "1. What is 4 + 3? Reference fallback-test",
        "1. 6",
        "Maths",
        {"year_group": 3, "age": 7},
        llm_client=RoutedLLM(),
    )

    assert result["success"] is True
    assert result["fallback_used"] is True
    assert result["model_used"] == "fallback-test-model"
    assert len(result["questions"]) == 3


def test_fallback_model_is_configurable_and_documented():
    source = Path("src/webapp/review_service.py").read_text(encoding="utf-8")
    assert 'os.getenv("FALLBACK_REVIEW_MODEL")' in source
    assert '"gemini-3.7-flash"' in source

    client_source = Path("src/llm_client.py").read_text(encoding="utf-8")
    assert 'os.getenv("FALLBACK_REVIEW_MODEL", "gemini-3.7-flash")' in client_source
    assert 'FALLBACK_REVIEW_PROVIDER' in client_source

    deploy_source = Path("deploy/deploy_gcp.sh").read_text(encoding="utf-8")
    assert 'FALLBACK_REVIEW_MODEL="${FALLBACK_REVIEW_MODEL:-gemini-3.7-flash}"' in deploy_source
