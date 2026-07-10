"""Lightweight front-end contract test without a browser dependency."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_tutor_review_payload_includes_question_index():
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")
    assert "question_index:" in javascript
    assert "hw.question_index" in javascript
    assert "currentQuestionIndex" in javascript
    assert "fetch('/api/review'" in javascript
