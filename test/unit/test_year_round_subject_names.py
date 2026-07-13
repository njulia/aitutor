from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_year_round_subject_keys_and_labels() -> None:
    from src.models import (
        ELEVEN_PLUS_YEAR_ROUND_SUBJECTS,
        canonical_year_round_subject,
        subject_display_name,
    )

    assert ELEVEN_PLUS_YEAR_ROUND_SUBJECTS == [
        "Maths-1year",
        "English-1year",
        "VerbalReasoning-1year",
        "NonVerbalReasoning-1year",
    ]
    assert canonical_year_round_subject("Verbal Reasoning") == "VerbalReasoning-1year"
    assert canonical_year_round_subject("Non-Verbal Reasoning") == "NonVerbalReasoning-1year"
    assert subject_display_name("Maths-1year") == "Maths"
    assert subject_display_name("NonVerbalReasoning-1year") == "Non-Verbal Reasoning"


def test_year_round_page_uses_internal_keys_but_friendly_labels() -> None:
    from pathlib import Path

    html = Path("static/elevenplus-year-round-plan.html").read_text(encoding="utf-8")
    assert "data.eleven_plus_year_round" in html
    assert "Maths-1year" in html
    assert "VerbalReasoning-1year" in html
    assert "function displaySubjectName(subject)" in html
