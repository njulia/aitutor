#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Safely delete and rebuild every question in the dedicated 11+ RAG store.

This is the 11+ counterpart to
``scripts/homework_generator/rebuild_all_homework.py``.  It rebuilds all three
browser content families without calling an LLM:

* ordinary 11+ practice (Maths, English, VR and NVR);
* the 55-set-per-subject catalogue used by
  ``static/elevenplus-topic-mastery.html``;
* the 52-week-per-subject year-round plan.

Deletion is permanent, so execution is deliberately two-step.  Run once with
no arguments to inspect the password-free target and planned counts, then copy
that target into ``--confirm-target`` and add ``--execute``.  A failed rebuild
can be resumed with ``--skip-clean`` because every generated document has a
stable ID.
"""
from __future__ import annotations

import argparse
import importlib
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOPIC_MASTERY_PAGE = PROJECT_ROOT / "static" / "elevenplus-topic-mastery.html"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

os.environ["TOKENIZERS_PARALLELISM"] = "false"


@dataclass(frozen=True)
class GeneratorSpec:
    family: str
    label: str
    subject_key: str
    module_name: str
    build_function: str
    expected_count: int


GENERATOR_SPECS = (
    GeneratorSpec("practice", "Maths", "Maths", "scripts.elevenplus.elevenplus_math_generator", "generate_11plus_batch", 1000),
    GeneratorSpec("practice", "English", "English", "scripts.elevenplus.elevenplus_english_generator", "generate_11plus_english_batch", 500),
    GeneratorSpec("practice", "Verbal Reasoning", "VerbalReasoning", "scripts.elevenplus.elevenplus_vr_generator", "generate_11plus_vr_batch", 300),
    GeneratorSpec("practice", "Non-Verbal Reasoning", "NonVerbalReasoning", "scripts.elevenplus.elevenplus_nvr_generator", "generate_11plus_nvr_batch", 300),
    GeneratorSpec("topic_mastery", "Maths", "Maths-topic-mastery", "scripts.elevenplus.elevenplus_math_topic_mastery_generator", "generate_topic_mastery_plan", 55),
    GeneratorSpec("topic_mastery", "English", "English-topic-mastery", "scripts.elevenplus.elevenplus_english_topic_mastery_generator", "generate_topic_mastery_plan", 55),
    GeneratorSpec("topic_mastery", "Verbal Reasoning", "VerbalReasoning-topic-mastery", "scripts.elevenplus.elevenplus_vr_topic_mastery_generator", "generate_topic_mastery_plan", 55),
    GeneratorSpec("topic_mastery", "Non-Verbal Reasoning", "NonVerbalReasoning-topic-mastery", "scripts.elevenplus.elevenplus_nvr_topic_mastery_generator", "generate_topic_mastery_plan", 55),
    GeneratorSpec("year_round", "Maths", "Maths-1year", "scripts.elevenplus.elevenplus_math_year_round_plan_generator", "build_plan_data", 52),
    GeneratorSpec("year_round", "English", "English-1year", "scripts.elevenplus.elevenplus_english_year_round_plan_generator", "build_plan_data", 52),
    GeneratorSpec("year_round", "Verbal Reasoning", "VerbalReasoning-1year", "scripts.elevenplus.elevenplus_vr_year_round_plan_generator", "build_plan_data", 52),
    GeneratorSpec("year_round", "Non-Verbal Reasoning", "NonVerbalReasoning-1year", "scripts.elevenplus.elevenplus_nvr_year_round_plan_generator", "build_plan_data", 52),
)


def discover_generators() -> list[GeneratorSpec]:
    """Validate and return the complete, ordered 11+ generator registry."""
    if not TOPIC_MASTERY_PAGE.is_file():
        raise RuntimeError(f"Missing topic-mastery page: {TOPIC_MASTERY_PAGE}")
    page = TOPIC_MASTERY_PAGE.read_text(encoding="utf-8")
    if "/api/elevenplus/topic-mastery/practice" not in page:
        raise RuntimeError("The topic-mastery page is not wired to its isolated practice endpoint")

    keys = [spec.subject_key for spec in GENERATOR_SPECS]
    if len(keys) != len(set(keys)):
        raise RuntimeError("The 11+ generator registry contains duplicate subject keys")
    return list(GENERATOR_SPECS)


def _scope_filters(spec: GeneratorSpec) -> dict[str, Any]:
    return {"year_group": 6, "subject": spec.subject_key, "content_type": spec.family}


def _normalise_topic_mastery_batch(raw_sets: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "content": item["content"],
            "metadata": item["metadata"],
            "doc_id": item["doc_id"],
        }
        for item in raw_sets
    ]


def _build_batch(spec: GeneratorSpec, general_count_override: int | None = None) -> list[dict[str, Any]]:
    """Run one deterministic generator without writing its optional plan files."""
    module = importlib.import_module(spec.module_name)
    builder = getattr(module, spec.build_function, None)
    if not callable(builder):
        raise RuntimeError(f"{spec.module_name} does not define {spec.build_function}()")

    if spec.family == "practice":
        count = general_count_override if general_count_override is not None else spec.expected_count
        batch = list(builder(count=count))
    elif spec.family == "topic_mastery":
        from src.elevenplus_topic_mastery import TOPIC_MASTERY_TOPICS

        module_topics = list(getattr(module, "TOPIC_LIST", []))
        if module_topics != TOPIC_MASTERY_TOPICS[spec.subject_key]:
            raise RuntimeError(
                f"{spec.label} generator topics do not match elevenplus-topic-mastery.html catalogue"
            )
        batch = _normalise_topic_mastery_batch(builder())
    elif spec.family == "year_round":
        plan = builder()
        rag_builder = getattr(module, "build_rag_batch", None)
        if not callable(rag_builder):
            raise RuntimeError(f"{spec.module_name} does not define build_rag_batch()")
        batch = list(rag_builder(plan))
    else:  # pragma: no cover - registry validation protects this branch
        raise RuntimeError(f"Unknown generator family: {spec.family}")

    _validate_batch(spec, batch, general_count_override)
    return batch


def _validate_batch(
    spec: GeneratorSpec,
    batch: Sequence[dict[str, Any]],
    general_count_override: int | None = None,
) -> None:
    from scripts.elevenplus.elevenplus_generator_utils import validate_homework_batch

    expected = (
        general_count_override
        if spec.family == "practice" and general_count_override is not None
        else spec.expected_count
    )
    if len(batch) != expected:
        raise RuntimeError(f"{spec.label} {spec.family}: expected {expected} records, got {len(batch)}")

    ids: set[str] = set()
    for item in batch:
        doc_id = str(item.get("doc_id") or "").strip()
        metadata = item.get("metadata") or {}
        if not doc_id or doc_id in ids:
            raise RuntimeError(f"{spec.label} {spec.family}: missing or duplicate document ID")
        ids.add(doc_id)
        if int(metadata.get("year_group") or 0) != 6:
            raise RuntimeError(f"{doc_id}: year_group must be 6")
        if metadata.get("subject") != spec.subject_key:
            raise RuntimeError(f"{doc_id}: expected subject {spec.subject_key!r}")
        if metadata.get("content_type") != spec.family:
            raise RuntimeError(f"{doc_id}: expected content_type {spec.family!r}")
        if not metadata.get("correct_answers"):
            raise RuntimeError(f"{doc_id}: missing private answer records")
        if not str(item.get("content") or "").strip():
            raise RuntimeError(f"{doc_id}: empty public question content")

    try:
        validate_homework_batch(batch)
    except ValueError as exc:
        raise RuntimeError(
            f"{spec.label} {spec.family}: question uniqueness validation failed: {exc}"
        ) from exc


def _target_counts(store: Any, specs: Sequence[GeneratorSpec]) -> dict[str, int]:
    return {
        spec.subject_key: store.store.count_by_metadata(_scope_filters(spec))
        for spec in specs
    }


def _delete_elevenplus_collection(store: Any) -> int:
    """Delete every record from the dedicated 11+ collection only."""
    before = int(store.store.count())
    deleted = int(store.store.delete_by_metadata({}))
    after = int(store.store.count())
    if after:
        raise RuntimeError(f"Deletion verification failed: {after} 11+ RAG records remain")
    if deleted != before:
        raise RuntimeError(f"Deletion count mismatch: expected {before}, database reported {deleted}")
    return deleted


def _expected_total(specs: Sequence[GeneratorSpec], general_count_override: int | None) -> int:
    return sum(
        general_count_override
        if spec.family == "practice" and general_count_override is not None
        else spec.expected_count
        for spec in specs
    )


def _generate_all(
    store: Any,
    specs: Sequence[GeneratorSpec],
    general_count_override: int | None,
) -> tuple[int, list[tuple[str, str]]]:
    from scripts.homework_generator.homework_generator_utils import add_homework_in_batches

    added_total = 0
    failures: list[tuple[str, str]] = []
    for position, spec in enumerate(specs, start=1):
        name = f"{spec.label} {spec.family.replace('_', ' ')}"
        print(f"\n[{position}/{len(specs)}] Rebuilding {name} using {spec.module_name.rsplit('.', 1)[-1]}.py")
        try:
            batch = _build_batch(spec, general_count_override)
            added = add_homework_in_batches(store, batch)
            added_total += added
            exact_count = store.store.count_by_metadata(_scope_filters(spec))
            print(f"{name}: {added} new records; database now contains {exact_count}")
        except Exception as exc:
            failures.append((name, str(exc)))
            print(f"ERROR rebuilding {name}: {exc}", file=sys.stderr)
    return added_total, failures


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely delete and rebuild ordinary, topic-mastery and year-round 11+ RAG questions."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform deletion and generation. Without this flag the command is a read-only plan.",
    )
    parser.add_argument(
        "--confirm-target",
        default="",
        help="Password-free database target printed by the planning run.",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Resume stable-ID generation without deleting the 11+ collection again.",
    )
    parser.add_argument(
        "--allow-sqlite",
        action="store_true",
        help="Allow an explicitly confirmed local SQLite target. PostgreSQL is required by default.",
    )
    parser.add_argument(
        "--count-per-general-subject",
        type=int,
        default=None,
        help="Override each ordinary-practice count (intended only for local tests).",
    )
    parser.add_argument(
        "--list-generators",
        action="store_true",
        help="List all generator families without opening a database connection.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.count_per_general_subject is not None and not 1 <= args.count_per_general_subject <= 10_000:
        raise SystemExit("--count-per-general-subject must be between 1 and 10000")

    specs = discover_generators()
    if args.list_generators:
        for spec in specs:
            print(f"{spec.family}: {spec.label} -> {spec.module_name.rsplit('.', 1)[-1]}.py")
        print(f"Topic-mastery page: {TOPIC_MASTERY_PAGE.relative_to(PROJECT_ROOT)}")
        return 0

    from src.elevenplus_rag import get_elevenplus_rag_store

    store = get_elevenplus_rag_store()
    target = store.store.database_target
    total_before = int(store.store.count())
    counts = _target_counts(store, specs)
    expected = _expected_total(specs, args.count_per_general_subject)

    print("\n11+ homework RAG rebuild plan")
    print(f"Database target: {target}")
    print(f"Collection: {store.store.collection_name}")
    print(f"Backend: {'PostgreSQL/pgvector' if store.store.is_postgres else 'SQLite'}")
    print(f"Current 11+ records: {total_before}")
    print(f"Generators: {len(specs)} (4 practice, 4 topic mastery, 4 year round)")
    print(f"Planned deterministic question sets: {expected}")
    print(f"Topic-mastery page: {TOPIC_MASTERY_PAGE.relative_to(PROJECT_ROOT)}")
    for spec in specs:
        print(f"- {spec.family}/{spec.label}: current={counts[spec.subject_key]}")
    print("Primary Year 1-6 homework uses a different collection and will not be touched.")

    if not args.execute:
        print("\nPLAN ONLY: no records were deleted or generated.")
        print("To run this exact rebuild, use:")
        print(
            "python scripts/elevenplus/rebuild_all_elevenplus.py "
            f"--execute --confirm-target {shlex.quote(target)}"
        )
        return 0

    if not store.store.is_postgres and not args.allow_sqlite:
        raise SystemExit(
            "Refusing to rebuild SQLite by default. Set PGVECTOR_DATABASE_URL or DATABASE_URL "
            "to PostgreSQL, or add --allow-sqlite for an intentional local test."
        )
    if args.confirm_target != target:
        raise SystemExit(
            "Database confirmation does not match. Run without --execute, then copy the exact "
            "password-free Database target into --confirm-target."
        )

    if args.skip_clean:
        print("\nSkipping deletion; resuming stable-ID generation.")
        deleted = 0
    else:
        print("\nDeleting every record from the dedicated 11+ RAG collection...")
        deleted = _delete_elevenplus_collection(store)
        print(f"Deletion verified: {deleted} records removed and 0 remain.")

    added, failures = _generate_all(store, specs, args.count_per_general_subject)
    final_total = int(store.store.count())
    final_counts = _target_counts(store, specs)

    print("\n11+ rebuild summary")
    print(f"Database target: {target}")
    print(f"Deleted: {deleted}")
    print(f"Newly inserted: {added}")
    print(f"Final 11+ records: {final_total}")
    for spec in specs:
        expected_count = (
            args.count_per_general_subject
            if spec.family == "practice" and args.count_per_general_subject is not None
            else spec.expected_count
        )
        print(f"- {spec.family}/{spec.label}: {final_counts[spec.subject_key]}/{expected_count}")

    incomplete = [
        spec
        for spec in specs
        if final_counts[spec.subject_key] < (
            args.count_per_general_subject
            if spec.family == "practice" and args.count_per_general_subject is not None
            else spec.expected_count
        )
    ]
    if failures or incomplete:
        if failures:
            print("Failed generators:", file=sys.stderr)
            for name, message in failures:
                print(f"- {name}: {message}", file=sys.stderr)
        if incomplete:
            print("Incomplete scopes: " + ", ".join(f"{item.family}/{item.label}" for item in incomplete), file=sys.stderr)
        print("Fix the errors, then rerun with --skip-clean and the same --confirm-target.")
        return 1

    if not args.skip_clean and final_total != expected:
        print(f"Expected exactly {expected} records after a clean rebuild, found {final_total}.", file=sys.stderr)
        return 1
    print("All 11+ practice, topic-mastery and year-round generators completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
