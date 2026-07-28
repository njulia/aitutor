"""Regression tests for 11+ question uniqueness and RAG compatibility."""
from __future__ import annotations

import ast
import contextlib
import importlib
import importlib.util
import inspect
import io
import json
import os
import re
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_DIR = PROJECT_ROOT / "scripts" / "elevenplus"

from scripts.elevenplus.elevenplus_generator_utils import (  # noqa: E402
    PUBLIC_FREE_RESOURCE_POLICY,
    homework_set_fingerprint,
    question_fingerprint,
    semantic_question_fingerprint,
    validate_homework_batch,
)


PRACTICE_GENERATORS = (
    (
        "scripts.elevenplus.elevenplus_math_generator",
        "generate_11plus_batch",
        1000,
    ),
    (
        "scripts.elevenplus.elevenplus_english_generator",
        "generate_11plus_english_batch",
        500,
    ),
    (
        "scripts.elevenplus.elevenplus_vr_generator",
        "generate_11plus_vr_batch",
        300,
    ),
    (
        "scripts.elevenplus.elevenplus_nvr_generator",
        "generate_11plus_nvr_batch",
        300,
    ),
)

YEAR_ROUND_GENERATORS = (
    "math",
    "english",
    "vr",
    "nvr",
)


def _answer_records(item: dict) -> list[dict]:
    return json.loads(item["metadata"]["correct_answers"])


def _stored_question_first_lines(content: str) -> list[str]:
    """Match the first-line identity check used by the shared RAG writer."""
    matches = list(re.finditer(r"(?m)^\d+\.\s+", content))
    blocks = [
        content[
            match.end() :
            matches[index + 1].start() if index + 1 < len(matches) else None
        ].strip()
        for index, match in enumerate(matches)
    ]
    return [
        " ".join(block.splitlines()[0].casefold().split())
        for block in blocks
    ]


def _rag_contract_path() -> Path | None:
    configured = os.getenv("ELEVENPLUS_RAG_CONTRACT_FILE")
    candidates = [
        Path(configured).resolve() if configured else None,
        GENERATOR_DIR.parents[1] / "src" / "elevenplus_rag.py",
        GENERATOR_DIR / "elevenplus_rag.py",
    ]
    return next((path for path in candidates if path and path.is_file()), None)


class ElevenPlusGeneratorUniquenessTests(unittest.TestCase):
    def test_full_practice_batches_are_unique_but_reuse_is_allowed(self) -> None:
        for module_name, function_name, expected_count in PRACTICE_GENERATORS:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                with contextlib.redirect_stdout(io.StringIO()):
                    batch = getattr(module, function_name)(count=expected_count)

                self.assertEqual(len(batch), expected_count)
                validate_homework_batch(batch)

                for item in batch:
                    records = _answer_records(item)
                    semantic_fingerprints = [
                        semantic_question_fingerprint(record)
                        for record in records
                    ]
                    self.assertEqual(
                        len(semantic_fingerprints),
                        len(set(semantic_fingerprints)),
                        item["doc_id"],
                    )

                    stored_stems = _stored_question_first_lines(item["content"])
                    self.assertEqual(len(stored_stems), 10, item["doc_id"])
                    self.assertEqual(
                        len(stored_stems),
                        len(set(stored_stems)),
                        item["doc_id"],
                    )

                set_fingerprints = [
                    homework_set_fingerprint(_answer_records(item))
                    for item in batch
                ]
                self.assertEqual(
                    len(set_fingerprints),
                    len(set(set_fingerprints)),
                )

                question_fingerprints = [
                    question_fingerprint(record)
                    for item in batch
                    for record in _answer_records(item)
                ]
                # Requirement 3: an individual question may legitimately be
                # reused in a different set; only whole-set duplication is
                # prohibited.
                self.assertLess(
                    len(set(question_fingerprints)),
                    len(question_fingerprints),
                )

    def test_year_round_sets_have_no_duplicate_questions_or_sets(self) -> None:
        for short_name in YEAR_ROUND_GENERATORS:
            with self.subTest(subject=short_name):
                module = importlib.import_module(
                    "scripts.elevenplus."
                    f"elevenplus_{short_name}_year_round_plan_generator"
                )
                plan = module.build_plan_data()
                rag_batch = module.build_rag_batch(plan)
                validate_homework_batch(rag_batch)
                self.assertEqual(len(rag_batch), 52)
                for item in rag_batch:
                    stored_stems = _stored_question_first_lines(item["content"])
                    self.assertEqual(len(stored_stems), 10, item["doc_id"])
                    self.assertEqual(
                        len(stored_stems),
                        len(set(stored_stems)),
                        item["doc_id"],
                    )

                week_sets: list[list[dict]] = []
                for term in plan:
                    for week in term["weeks"]:
                        records = [
                            {
                                "question": (
                                    f"{question['id']}. "
                                    f"{question['questionText']}"
                                ),
                                "options": question["options"],
                                "correct_letter": question["correctLetter"],
                                "answer": question["correctValue"],
                            }
                            for question in week["homeworkSet"]
                        ]
                        self.assertEqual(
                            len({question_fingerprint(record) for record in records}),
                            10,
                        )
                        week_sets.append(records)

                self.assertEqual(len(week_sets), 52)
                self.assertEqual(
                    len({homework_set_fingerprint(records) for records in week_sets}),
                    52,
                )

    def test_topic_mastery_sets_have_no_duplicate_questions_or_sets(self) -> None:
        for short_name in YEAR_ROUND_GENERATORS:
            with self.subTest(subject=short_name):
                module = importlib.import_module(
                    "scripts.elevenplus."
                    f"elevenplus_{short_name}_topic_mastery_generator"
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    mastery_sets = module.generate_topic_mastery_plan()

                self.assertEqual(len(mastery_sets), 55)
                validate_homework_batch(mastery_sets)
                signatures = []
                for item in mastery_sets:
                    records = item["questions"]
                    stored_stems = _stored_question_first_lines(item["content"])
                    self.assertEqual(len(stored_stems), 10, item["doc_id"])
                    self.assertEqual(
                        len(stored_stems),
                        len(set(stored_stems)),
                        item["doc_id"],
                    )
                    self.assertEqual(
                        len({question_fingerprint(record) for record in records}),
                        10,
                    )
                    signatures.append(homework_set_fingerprint(records))
                self.assertEqual(len(signatures), len(set(signatures)))

    def test_generators_have_no_network_or_paid_question_bank_dependency(self) -> None:
        self.assertEqual(
            PUBLIC_FREE_RESOURCE_POLICY,
            "original-content-and-public-free-guidance-only",
        )
        forbidden_roots = {
            "bs4",
            "httpx",
            "requests",
            "scrapy",
            "selenium",
            "urllib",
        }
        for path in GENERATOR_DIR.glob("elevenplus*_generator.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported_roots: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(
                        alias.name.split(".", 1)[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".", 1)[0])
            self.assertFalse(
                imported_roots.intersection(forbidden_roots),
                f"{path.name} must not fetch external question content",
            )

    def test_query_rag_api_and_result_shapes_are_unchanged(self) -> None:
        rag_path = _rag_contract_path()
        if rag_path is None:
            self.skipTest("elevenplus_rag.py is not present in this archive")

        spec = importlib.util.spec_from_file_location(
            "src._elevenplus_rag_contract_fixture",
            rag_path,
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        expected_parameters = {
            "search_homework": [
                "query",
                "year_group",
                "subject",
                "homework_minutes",
                "study_year_month",
                "k",
            ],
            "search_homework_by_metadata": [
                "year_group",
                "subject",
                "k",
                "week_num",
                "content_type",
                "mastery_set_index",
                "offset",
                "exclude_ids",
            ],
            "get_homework_questions": ["doc_id", "content"],
            "search_homework_answers": ["doc_id"],
        }
        for function_name, parameter_names in expected_parameters.items():
            signature = inspect.signature(getattr(module, function_name))
            self.assertEqual(list(signature.parameters), parameter_names)

        class FakeStore:
            @staticmethod
            def search(*, query_embedding, k, filters):
                return [
                    {
                        "doc_id": "doc-1",
                        "content": "content",
                        "metadata": {"subject": "Maths"},
                        "distance": 0.25,
                        "similarity": 0.75,
                    }
                ]

            @staticmethod
            def get_by_metadata(*, filters, k, offset=0, exclude_ids=None):
                return [
                    {
                        "doc_id": "doc-1",
                        "content": "content",
                        "metadata": {"subject": "Maths"},
                    }
                ]

        store = module.ElevenPlusRAGStore.__new__(module.ElevenPlusRAGStore)
        store.store = FakeStore()
        store._embedding_function = lambda texts: [[0.0]]

        search_result = store.search("maths", k=5)
        self.assertEqual(
            set(search_result[0]),
            {
                "doc_id",
                "content",
                "metadata",
                "score",
                "distance",
                "similarity",
            },
        )
        metadata_result = store.search_by_metadata(
            {"year_group": 6, "subject": "Maths"},
            k=5,
        )
        self.assertEqual(
            set(metadata_result[0]),
            {"doc_id", "content", "metadata"},
        )


if __name__ == "__main__":
    unittest.main()
