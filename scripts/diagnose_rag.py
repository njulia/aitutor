#!/usr/bin/env python
"""Show which database the app is reading and whether exact RAG rows exist."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

from src.homework_rag import get_homework_rag_store
from src.elevenplus_rag import (
    get_elevenplus_rag_store,
    search_homework_by_metadata as search_elevenplus_by_metadata,
    count_homework_by_metadata as count_elevenplus_by_metadata,
)
from src.webapp.homework_assignment_store import get_assignment_store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2)
    parser.add_argument("--subject", default="Maths")
    parser.add_argument("--learner", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--collection",
        choices=("primary", "elevenplus"),
        default="primary",
        help="RAG collection to inspect",
    )
    parser.add_argument("--week", type=int, default=0)
    parser.add_argument("--content-type", default="")
    args = parser.parse_args()

    if args.collection == "elevenplus":
        rag = get_elevenplus_rag_store()
        total = count_elevenplus_by_metadata(
            args.year,
            args.subject,
            week_num=args.week or None,
            content_type=args.content_type or None,
        )
        samples = search_elevenplus_by_metadata(
            args.year,
            args.subject,
            k=max(1, min(args.limit, 20)),
            week_num=args.week or None,
            content_type=args.content_type or None,
        )
        content_kind = f"elevenplus_week_{args.week:02d}" if args.week else "elevenplus"
    else:
        rag = get_homework_rag_store()
        filters = {"year_group": args.year, "subject": args.subject}
        total = rag.store.count_by_metadata(filters)
        samples = rag.search_by_metadata(filters, k=max(1, min(args.limit, 20)))
        content_kind = "primary"

    source = "PGVECTOR_DATABASE_URL" if os.getenv("PGVECTOR_DATABASE_URL") else (
        "DATABASE_URL" if os.getenv("DATABASE_URL") else "SQLite fallback"
    )
    print(f"RAG URL source: {source}")
    print(f"RAG database: {rag.store.database_target}")
    print(f"Collection: {rag.store.collection_name}")
    print(f"Exact {args.subject} Year {args.year} rows: {total}")
    for item in samples:
        print(json.dumps({
            "doc_id": item.get("doc_id"),
            "metadata": item.get("metadata"),
            "content_preview": str(item.get("content") or "")[:100],
        }, ensure_ascii=False))

    if args.learner:
        assignment_store = get_assignment_store()
        seen = assignment_store.seen_doc_ids(
            args.learner,
            subject=args.subject,
            year_group=args.year,
            content_kind=content_kind,
            limit=20_000,
        )
        if args.collection == "elevenplus":
            unseen = search_elevenplus_by_metadata(
                args.year,
                args.subject,
                k=1,
                week_num=args.week or None,
                content_type=args.content_type or None,
                exclude_ids=seen,
            )
        else:
            unseen = rag.search_by_metadata(filters, k=1, exclude_ids=seen)
        print(f"Already assigned to {args.learner!r}: {len(seen)}")
        print(f"At least one unseen exact row: {bool(unseen)}")


if __name__ == "__main__":
    main()
