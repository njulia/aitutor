"""Regression tests for worksheet and RAG-shape uniqueness guarantees."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_DIR = PROJECT_ROOT / "scripts" / "homework_generator"

from scripts.homework_generator.homework_generator_utils import (  # noqa: E402
    PUBLIC_FREE_RESOURCE_POLICY,
    build_batch_item,
    make_mcq,
    render_homework,
    stable_random,
    validate_homework_items,
)


def _question_blocks(content: str) -> list[str]:
    matches = list(re.finditer(r"(?m)^\d+\.\s+", content))
    return [
        content[match.end() : matches[i + 1].start() if i + 1 < len(matches) else None].strip()
        for i, match in enumerate(matches)
    ]


def _stems(content: str) -> list[str]:
    return [block.splitlines()[0].casefold() for block in _question_blocks(content)]


def _repeated_pairs(index: int) -> list[tuple[str, str]]:
    rng = stable_random("Science", 3, "Plants", index)
    base = [
        (
            "Which part absorbs water from the soil?",
            "roots",
            ["flowers", "fruit", "petals"],
        ),
        (
            "Which part usually makes seeds?",
            "flower",
            ["root", "soil", "stone"],
        ),
    ]
    return [
        make_mcq(*base[offset % len(base)], rng)
        for offset in range(10)
    ]


class HomeworkUniquenessTests(unittest.TestCase):
    def test_repeated_source_prompts_become_ten_distinct_questions(self) -> None:
        content, answers = render_homework(
            "Science", 3, "Plants", 7, _repeated_pairs(7)
        )

        self.assertEqual(len(_question_blocks(content)), 10)
        self.assertEqual(len(_stems(content)), len(set(_stems(content))))
        self.assertEqual(len(answers), 10)

    def test_different_sets_are_not_identical_but_can_share_a_question(self) -> None:
        first, _ = render_homework("Science", 3, "Plants", 1, _repeated_pairs(1))
        second, _ = render_homework("Science", 3, "Plants", 2, _repeated_pairs(2))

        self.assertNotEqual(_question_blocks(first), _question_blocks(second))
        shared = {
            "which part absorbs water from the soil?",
            "which part usually makes seeds?",
        }.intersection(_stems(first)).intersection(_stems(second))
        self.assertTrue(shared)

    def test_rag_item_contract_is_unchanged(self) -> None:
        content, answers = render_homework(
            "Science", 3, "Plants", 1, _repeated_pairs(1)
        )
        item = build_batch_item(
            content=content,
            answers=answers,
            year_group=3,
            subject="Science",
            topic="Plants",
            homework_minutes="15-20",
            key_stage="KS2",
            doc_id="science_y3_0001",
        )

        self.assertEqual(set(item), {"content", "metadata", "doc_id"})
        self.assertEqual(
            set(item["metadata"]),
            {
                "year_group",
                "subject",
                "homework_minutes",
                "key_stage",
                "topic",
                "student_id",
                "correct_answers",
            },
        )
        self.assertEqual(
            json.loads(item["metadata"]["correct_answers"]),
            answers,
        )
        validate_homework_items([item])

    def test_identical_homework_sets_are_rejected_before_rag_write(self) -> None:
        content, answers = render_homework(
            "Science", 3, "Plants", 1, _repeated_pairs(1)
        )
        common = dict(
            content=content,
            answers=answers,
            year_group=3,
            subject="Science",
            topic="Plants",
            homework_minutes="15-20",
            key_stage="KS2",
        )
        first = build_batch_item(**common, doc_id="first")
        second = build_batch_item(**common, doc_id="second")

        with self.assertRaisesRegex(ValueError, "identical"):
            validate_homework_items([first, second])

    def test_content_policy_uses_only_original_and_open_material(self) -> None:
        self.assertEqual(
            PUBLIC_FREE_RESOURCE_POLICY,
            "original-content-and-open-government-curriculum",
        )


if __name__ == "__main__":
    unittest.main()
