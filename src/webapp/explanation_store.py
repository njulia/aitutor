"""Shared, learner-safe persistence for reusable question explanations.

Only the reusable explanation and a one-way question fingerprint are stored.
Student answers, names, account identifiers and correct-answer text are never
stored in this table.
"""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, UniqueConstraint, insert, select, update
from sqlalchemy.exc import IntegrityError

from .db import get_engine, normalise_database_url

_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "aitutor.db")
_URL = normalise_database_url(
    os.getenv("PROGRESS_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite+pysqlite:///{_DEFAULT}"
)
_engine = get_engine(_URL)
_metadata = MetaData()

question_explanations = Table(
    "question_explanations",
    _metadata,
    Column("id", String(80), primary_key=True),
    Column("question_hash", String(64), nullable=False),
    Column("subject", String(80), nullable=False),
    Column("year_group", Integer, nullable=False, default=3),
    Column("is_eleven_plus", Integer, nullable=False, default=0),
    Column("explanation", Text, nullable=False),
    Column("model_used", String(160), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("question_hash", name="uq_question_explanation_hash"),
)


def init_explanation_db() -> None:
    _metadata.create_all(_engine)


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def question_hash(
    question: str,
    subject: str,
    *,
    correct_answer: str = "",
    is_eleven_plus: bool = False,
) -> str:
    """Create a stable fingerprint without storing the answer text."""
    payload = "\x1f".join(
        [
            _normalise(subject),
            "11plus" if is_eleven_plus else "primary",
            _normalise(question),
            hashlib.sha256(_normalise(correct_answer).encode("utf-8")).hexdigest()
            if correct_answer else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_explanation(question_key: str) -> Optional[dict]:
    init_explanation_db()
    with _engine.connect() as conn:
        row = conn.execute(
            select(question_explanations).where(question_explanations.c.question_hash == question_key)
        ).mappings().first()
    return dict(row) if row else None


def save_explanation(
    question_key: str,
    *,
    subject: str,
    year_group: int,
    is_eleven_plus: bool,
    explanation: str,
    model_used: Optional[str],
) -> dict:
    """Insert once, or safely reuse the existing shared explanation."""
    init_explanation_db()
    now = datetime.now(UTC)
    values = {
        "id": uuid.uuid4().hex,
        "question_hash": question_key,
        "subject": str(subject or "")[:80],
        "year_group": max(1, min(int(year_group or 3), 6)),
        "is_eleven_plus": 1 if is_eleven_plus else 0,
        "explanation": str(explanation or "").strip(),
        "model_used": str(model_used or "")[:160] or None,
        "created_at": now,
        "updated_at": now,
    }
    if not values["explanation"]:
        raise ValueError("Explanation cannot be empty")

    try:
        with _engine.begin() as conn:
            conn.execute(insert(question_explanations).values(**values))
    except IntegrityError:
        # Another request may have generated the same question concurrently.
        # Prefer the already-persisted shared explanation.
        existing = get_explanation(question_key)
        if existing:
            return existing
        raise
    return values
