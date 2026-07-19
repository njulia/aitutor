from __future__ import annotations

import importlib

import pytest

from src.webapp.question_utils import parse_public_questions

pytestmark = pytest.mark.unit


GENERATORS = {
    "German": ("homework_german_generator", "generate_german_homework", "GERMAN_TOPICS_BY_YEAR"),
    "Italian": ("homework_italian_generator", "generate_italian_homework", "ITALIAN_TOPICS_BY_YEAR"),
    "Polish": ("homework_polish_generator", "generate_polish_homework", "POLISH_TOPICS_BY_YEAR"),
    "Arabic": ("homework_arabic_generator", "generate_arabic_homework", "ARABIC_TOPICS_BY_YEAR"),
    "Music": ("homework_music_generator", "generate_music_homework", "MUSIC_TOPICS_BY_YEAR"),
    "Physical Education": (
        "homework_physical_education_generator",
        "generate_physical_education_homework",
        "PHYSICAL_EDUCATION_TOPICS_BY_YEAR",
    ),
    "Religious Education": (
        "homework_religious_education_generator",
        "generate_religious_education_homework",
        "RELIGIOUS_EDUCATION_TOPICS_BY_YEAR",
    ),
    "PSHE": ("homework_pshe_generator", "generate_pshe_homework", "PSHE_TOPICS_BY_YEAR"),
}


@pytest.mark.parametrize("subject", GENERATORS)
@pytest.mark.parametrize("year_group", range(1, 7))
def test_additional_subject_generator_contract(subject: str, year_group: int) -> None:
    module_name, function_name, topics_name = GENERATORS[subject]
    module = importlib.import_module(f"scripts.homework_generator.{module_name}")
    topic = getattr(module, topics_name)[year_group][0]

    content, answers = getattr(module, function_name)(year_group, topic, 1)
    questions = parse_public_questions(content)

    assert content.startswith(f"{subject} Homework - Year {year_group}")
    assert len(answers) == 10
    assert len(questions) == 10
    assert all(question["response_type"] == "single_choice" for question in questions)
    assert all(len(question["options"]) == 4 for question in questions)


@pytest.mark.parametrize("subject", GENERATORS)
def test_additional_subject_batch_metadata(subject: str) -> None:
    module_name, _function_name, _topics_name = GENERATORS[subject]
    module = importlib.import_module(f"scripts.homework_generator.{module_name}")

    item = module.generate_year_homework(3, count=1)[0]

    assert item["metadata"]["subject"] == subject
    assert item["metadata"]["year_group"] == 3
    assert item["metadata"]["correct_answers"]
    assert item["doc_id"].endswith("_y3_0001")


def test_picker_subjects_have_new_generator_modules() -> None:
    from src.models import UK_PRIMARY_SUBJECTS

    for subject in GENERATORS:
        assert subject in UK_PRIMARY_SUBJECTS

