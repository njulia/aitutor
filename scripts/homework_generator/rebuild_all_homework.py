#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Delete and rebuild all Year 1-6 primary homework in the configured RAG store.

The command is intentionally two-step because deletion is permanent:

1. Run without ``--execute`` to inspect the password-free database target,
   discovered subjects and deletion counts.
2. Copy the displayed target into ``--confirm-target`` and add ``--execute``.

The 11+ collection is not touched. Generator writes are deterministic and
idempotent, so a failed rebuild can be resumed with ``--skip-clean``.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from src.models import canonical_primary_subject


@dataclass(frozen=True)
class GeneratorSpec:
    module_name: str
    file_name: str
    subject: str


def discover_generators() -> list[GeneratorSpec]:
    """Discover every concrete ``homework_*_generator.py`` subject module."""
    specs: list[GeneratorSpec] = []
    seen_subjects: set[str] = set()
    for path in sorted(GENERATOR_DIR.glob("homework_*_generator.py")):
        raw_name = path.stem.removeprefix("homework_").removesuffix("_generator")
        subject = canonical_primary_subject(raw_name.replace("_", " "))
        if not subject:
            raise RuntimeError(
                f"Cannot map {path.name} to an allowed primary subject. "
                "Add the subject alias to src/models.py before rebuilding."
            )
        if subject in seen_subjects:
            raise RuntimeError(f"More than one generator resolves to {subject!r}")
        seen_subjects.add(subject)
        specs.append(GeneratorSpec(
            module_name=f"scripts.homework_generator.{path.stem}",
            file_name=path.name,
            subject=subject,
        ))
    if not specs:
        raise RuntimeError(f"No subject generators found in {GENERATOR_DIR}")
    return specs


def _selected_generators(specs: Sequence[GeneratorSpec], requested: Sequence[str]) -> list[GeneratorSpec]:
    if not requested:
        return list(specs)
    wanted: set[str] = set()
    for value in requested:
        subject = canonical_primary_subject(value)
        if not subject:
            raise ValueError(f"Unknown primary subject: {value}")
        wanted.add(subject)
    selected = [spec for spec in specs if spec.subject in wanted]
    missing = wanted - {spec.subject for spec in selected}
    if missing:
        raise ValueError(f"No generator file found for: {', '.join(sorted(missing))}")
    return selected


def _load_generator(spec: GeneratorSpec):
    module = importlib.import_module(spec.module_name)
    if not callable(getattr(module, "generate_year_homework", None)):
        raise RuntimeError(f"{spec.file_name} does not define generate_year_homework()")
    counts = getattr(module, "HOMEWORK_COUNT", None)
    if not isinstance(counts, dict) or any(year not in counts for year in range(1, 7)):
        raise RuntimeError(f"{spec.file_name} must define HOMEWORK_COUNT for Years 1-6")
    return module


def _target_counts(store: Any) -> dict[int, int]:
    return {
        year: store.store.count_by_metadata({"year_group": year})
        for year in range(1, 7)
    }


def _delete_primary_years(store: Any) -> int:
    """Delete every Year 1-6 row from the primary homework collection only."""
    deleted_total = 0
    for year in range(1, 7):
        deleted = store.store.delete_by_metadata({"year_group": year})
        deleted_total += deleted
        print(f"Deleted Year {year}: {deleted} homework records")
    return deleted_total


def _expected_total(specs: Sequence[GeneratorSpec], count_override: int | None) -> int:
    total = 0
    for spec in specs:
        module = _load_generator(spec)
        for year in range(1, 7):
            total += count_override if count_override is not None else int(module.HOMEWORK_COUNT[year])
    return total


def _generate_all(
    store: Any,
    specs: Sequence[GeneratorSpec],
    count_override: int | None,
) -> tuple[int, list[tuple[str, str]]]:
    from scripts.homework_generator.homework_generator_utils import add_homework_in_batches

    added_total = 0
    failures: list[tuple[str, str]] = []
    for position, spec in enumerate(specs, start=1):
        print(f"\n[{position}/{len(specs)}] Rebuilding {spec.subject} using {spec.file_name}")
        try:
            module = _load_generator(spec)
            for year in range(1, 7):
                count = count_override if count_override is not None else int(module.HOMEWORK_COUNT[year])
                print(f"{spec.subject} Year {year}: preparing {count} worksheets")
                homework = module.generate_year_homework(year, count)
                if len(homework) != count:
                    raise RuntimeError(
                        f"expected {count} generated records for Year {year}, got {len(homework)}"
                    )
                added = add_homework_in_batches(store, homework)
                added_total += added
                exact_count = store.store.count_by_metadata({
                    "year_group": year,
                    "subject": spec.subject,
                })
                print(
                    f"{spec.subject} Year {year}: {added} new records; "
                    f"database now contains {exact_count}"
                )
        except Exception as exc:
            failures.append((spec.subject, str(exc)))
            print(f"ERROR rebuilding {spec.subject}: {exc}", file=sys.stderr)
    return added_total, failures


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely delete and rebuild all Year 1-6 primary homework in RAG."
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
        help="Resume idempotent generation without deleting the primary collection again.",
    )
    parser.add_argument(
        "--allow-sqlite",
        action="store_true",
        help="Allow an explicitly confirmed local SQLite target. PostgreSQL is required by default.",
    )
    parser.add_argument(
        "--count-per-year",
        type=int,
        default=None,
        help="Override every generator's production count (useful only for local tests).",
    )
    parser.add_argument(
        "--subject",
        action="append",
        default=[],
        help="Rebuild only this subject; repeat the option for more than one. Default: all.",
    )
    parser.add_argument(
        "--list-generators",
        action="store_true",
        help="List discovered generator files without opening a database connection.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.count_per_year is not None and not 1 <= args.count_per_year <= 10_000:
        raise SystemExit("--count-per-year must be between 1 and 10000")

    specs = _selected_generators(discover_generators(), args.subject)
    if args.list_generators:
        for spec in specs:
            print(f"{spec.subject}: {spec.file_name}")
        return 0

    from src.homework_rag import get_homework_rag_store

    store = get_homework_rag_store()
    target = store.store.database_target
    counts = _target_counts(store)
    expected = _expected_total(specs, args.count_per_year)

    print("\nPrimary homework RAG rebuild plan")
    print(f"Database target: {target}")
    print(f"Collection: {store.store.collection_name}")
    print(f"Backend: {'PostgreSQL/pgvector' if store.store.is_postgres else 'SQLite'}")
    print("Current Year 1-6 records: " + ", ".join(f"Y{year}={counts[year]}" for year in range(1, 7)))
    print(f"Generators ({len(specs)}): " + ", ".join(spec.subject for spec in specs))
    print(f"Planned deterministic worksheets: {expected}")
    print("11+ homework is stored separately and will not be deleted.")

    if not args.execute:
        print("\nPLAN ONLY: no records were deleted or generated.")
        print("To run this exact rebuild, use:")
        print(
            "python scripts/homework_generator/rebuild_all_homework.py "
            f"--execute --confirm-target {target!r}"
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
        print("\nSkipping deletion; resuming idempotent generation.")
        deleted = 0
    else:
        print("\nDeleting Year 1-6 records from the primary homework collection...")
        deleted = _delete_primary_years(store)
        remaining = sum(_target_counts(store).values())
        if remaining:
            raise RuntimeError(f"Deletion verification failed: {remaining} Year 1-6 records remain")
        print(f"Deletion verified: {deleted} records removed and 0 remain.")

    added, failures = _generate_all(store, specs, args.count_per_year)
    final_counts = _target_counts(store)
    print("\nRebuild summary")
    print(f"Database target: {target}")
    print(f"Deleted: {deleted}")
    print(f"Newly inserted: {added}")
    print("Final Year 1-6 records: " + ", ".join(f"Y{year}={final_counts[year]}" for year in range(1, 7)))
    if failures:
        print("Failed subjects:", file=sys.stderr)
        for subject, message in failures:
            print(f"- {subject}: {message}", file=sys.stderr)
        print("Fix the errors, then rerun with --skip-clean and the same --confirm-target.")
        return 1
    print("All discovered primary subject generators completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

