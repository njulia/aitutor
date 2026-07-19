#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate deterministic Music homework for England Years 1-6."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

from src.homework_rag import get_homework_rag_store
from scripts.homework_generator.homework_additional_subjects import (
    HOMEWORK_COUNT, generate_subject_homework, generate_subject_year,
    populate_subject, topics_for_subject,
)

SUBJECT = "Music"
SLUG = "music"
MUSIC_TOPICS_BY_YEAR = {year: topics_for_subject(SUBJECT, year) for year in range(1, 7)}


def generate_music_homework(year_group: int, topic: str, index: int) -> tuple[str, list[str]]:
    return generate_subject_homework(SUBJECT, year_group, topic, index)


def generate_year_homework(year_group: int, count: int = 300) -> list[dict]:
    return generate_subject_year(SUBJECT, SLUG, year_group, count)


def main() -> None:
    populate_subject(get_homework_rag_store(), SUBJECT, SLUG)


if __name__ == "__main__":
    main()

