from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.cache import review_cache
from src.webapp import review_service

pytestmark = pytest.mark.unit


class FailingLLM:
    provider = "api"
    model = "unavailable-model"

    def complete(self, *_args, **_kwargs):
        raise RuntimeError("temporary provider failure")


class EmptyLLM:
    provider = "api"
    model = "empty-model"

    def complete(self, *_args, **_kwargs):
        return ""


def _stub_rag_marking(monkeypatch) -> None:
    monkeypatch.setattr(
        review_service,
        "_load_rag_answers",
        lambda *_args: [
            {"question": "1. What is 2 + 2?", "answer": "4"},
            {"question": "2. What is 5 - 2?", "answer": "3"},
        ],
    )
    monkeypatch.setattr(
        review_service,
        "_prepare_solution_methods",
        lambda *_args, **_kwargs: ({}, {}, []),
    )
    monkeypatch.setattr(
        review_service,
        "_finish_solution_methods",
        lambda *_args, **_kwargs: [],
    )


@pytest.mark.parametrize("llm_client", [FailingLLM(), EmptyLLM(), None])
def test_rag_review_keeps_summary_and_score_when_llm_is_unavailable(
    monkeypatch, llm_client
) -> None:
    _stub_rag_marking(monkeypatch)
    review_cache.clear()

    result = review_service.review_homework(
        "1. What is 2 + 2?\n2. What is 5 - 2?",
        "1. 4\n2. 4",
        "Maths",
        {"year_group": 2, "age": 6},
        quick_review=True,
        homework_doc_id=f"rag-fallback-{uuid.uuid4().hex}",
        llm_client=llm_client,
    )

    assert result["success"] is True
    assert result["from_rag_answers"] is True
    assert result["llm_fallback"] is True
    assert result["score"] == 1.0
    assert result["max_score"] == 2
    assert result["correct_count"] == 1
    assert result["attempted"] == 2
    assert "## Review Summary" in result["review"]
    assert "| ✅ | 1. What is 2 + 2? | 4 | 4 |" in result["review"]
    assert "| ❌ | 2. What is 5 - 2? | 4 | 3 |" in result["review"]
    assert "**Score: 1/2**" in result["review"]
    assert result["display_review"] in result["review"]
    assert result["llm_response"] == ""


def test_review_ui_prefers_fallback_display_with_table_and_score() -> None:
    source = Path("static/js/app.js").read_text(encoding="utf-8")

    assert source.count(
        "data.display_review || data.llm_response || data.review"
    ) == 2


@pytest.mark.parametrize(
    ("path", "brand_markup"),
    [
        (
            "static/app.html",
            '<a class="logo" href="/" aria-label="Homework Magic home">',
        ),
        (
            "static/progress.html",
            '<a class="logo" href="/" aria-label="Homework Magic home">',
        ),
        (
            "static/elevenplus-year-round-plan.html",
            '<a class="brand" href="/">✨ Homework Magic</a>',
        ),
        (
            "static/safety.html",
            '<a href="/" aria-label="Homework Magic home">✨ Homework Magic</a>',
        ),
    ],
)
def test_header_brand_links_home_without_duplicate_home_menu(
    path: str, brand_markup: str
) -> None:
    source = Path(path).read_text(encoding="utf-8")
    brand_start = source.index(brand_markup)
    nav_end = source.index("</nav>", brand_start)
    header = source[brand_start:nav_end]

    assert brand_markup in header
    assert 'href="/">Home</a>' not in header
