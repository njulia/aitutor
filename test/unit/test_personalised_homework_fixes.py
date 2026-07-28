from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def test_generated_payload_unwraps_double_encoded_json_and_newlines() -> None:
    from src.homework_generator import _extract_generated_payload

    payload = {
        "homework": "1. Translate hello into French.\n2. Translate goodbye into French.",
        "correct_answers": [
            {"question": "1", "answer": "bonjour"},
            {"question": "2", "answer": "au revoir"},
        ],
    }
    double_encoded = json.dumps(json.dumps(payload))

    homework, answers = _extract_generated_payload(double_encoded, "French")

    assert homework == "1. Translate hello into French.\n2. Translate goodbye into French."
    assert [item["answer"] for item in answers] == ["bonjour", "au revoir"]
    assert not homework.lstrip().startswith("{")
    assert "\\n" not in homework


def test_public_homework_content_repairs_legacy_json_wrappers() -> None:
    from src.webapp.question_utils import public_homework_content

    legacy = json.dumps({
        "homework": "1. Write the missing word.\\n2. Match the greeting.",
        "correct_answers": [{"question": "1", "answer": "bonjour"}],
    })

    public = public_homework_content(legacy)

    assert public == "1. Write the missing word.\n2. Match the greeting."
    assert "correct_answers" not in public
    assert "\\n" not in public


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("Year 4 French greetings", ["French"]),
        ("A little German practice", ["German"]),
        ("Year 3 Italian colours", ["Italian"]),
        ("Practise Polish words", ["Polish"]),
        ("Year 5 Arabic vocabulary", ["Arabic"]),
        ("Help with fractions", ["Maths"]),
    ],
)
def test_supported_primary_subjects_are_extracted(request_text: str, expected: list[str]) -> None:
    from src.models import extract_primary_subjects

    assert extract_primary_subjects(request_text) == expected


def test_browser_source_persists_primary_and_eleven_plus_choices() -> None:
    from pathlib import Path

    source = (Path(__file__).parents[2] / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "homeworkMagic.learningChoices.v1" in source
    assert "homeworkSubject" in source
    assert "elevenSubject" in source
    assert "homeworkYear" in source
    assert "localStorage.setItem(LEARNING_CHOICES_KEY" in source


def test_browser_source_removes_legacy_free_text_and_keeps_notes_ephemeral() -> None:
    from pathlib import Path

    source = (Path(__file__).parents[2] / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "delete existing.homeworkPrompt" in source
    assert "delete saved.elevenPrompt" in source
    assert "restoreLearningChoices();" in source
    save_choices_body = source.split("function saveLearningChoices()", 1)[1].split(
        "function restoreLearningChoices()", 1
    )[0]
    assert "homework-parent-notes" not in save_choices_body
    assert "eleven-parent-notes" not in save_choices_body
