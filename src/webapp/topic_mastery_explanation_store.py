"""Persistent, question-level explanations for 11+ Topic Mastery.

Explanations are shared across students because they are tied to the stable
question identity, not to a pupil's answer. No student answer is stored.
"""
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Text, UniqueConstraint, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .db import get_engine, normalise_database_url

_DEFAULT_SQLITE = Path(__file__).resolve().parents[2] / "data" / "topic_mastery_explanations.db"


def _engine() -> Engine:
    url = normalise_database_url(
        os.getenv("DATABASE_URL")
        or os.getenv("MEMORY_DATABASE_URL")
        or f"sqlite+pysqlite:///{_DEFAULT_SQLITE}"
    )
    return get_engine(url)


_METADATA = MetaData()
_TABLE = __import__("sqlalchemy").Table(
    "elevenplus_topic_mastery_explanations",
    _METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("question_key", String(64), nullable=False),
    Column("doc_id", String(256), nullable=False),
    Column("subject", String(80), nullable=False),
    Column("topic", String(200), nullable=False),
    Column("mastery_level", Integer, nullable=False),
    Column("question_index", Integer, nullable=False),
    Column("explanation", Text, nullable=False),
    Column("model_used", String(200), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("question_key", name="uq_topic_mastery_explanation_key"),
)


def init_topic_mastery_explanation_store() -> None:
    engine = _engine()
    _METADATA.create_all(engine)


def question_key(
    *,
    doc_id: str,
    subject: str,
    topic: str,
    mastery_level: int,
    question_index: int,
    question: str,
) -> str:
    canonical = " ".join(str(question or "").split()).casefold()
    raw = "|".join([
        str(doc_id or ""),
        str(subject or ""),
        str(topic or ""),
        str(mastery_level),
        str(question_index),
        canonical,
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_explanation(key: str) -> Optional[dict]:
    init_topic_mastery_explanation_store()
    with _engine().connect() as conn:
        row = conn.execute(
            select(_TABLE).where(_TABLE.c.question_key == key)
        ).mappings().first()
    return dict(row) if row else None


def save_explanation(
    *,
    key: str,
    doc_id: str,
    subject: str,
    topic: str,
    mastery_level: int,
    question_index: int,
    explanation: str,
    model_used: Optional[str],
) -> dict:
    init_topic_mastery_explanation_store()
    now = datetime.now(UTC)
    engine = _engine()
    values = {
        "question_key": key,
        "doc_id": str(doc_id),
        "subject": str(subject),
        "topic": str(topic),
        "mastery_level": int(mastery_level),
        "question_index": int(question_index),
        "explanation": str(explanation).strip(),
        "model_used": model_used,
        "created_at": now,
        "updated_at": now,
    }
    with engine.begin() as conn:
        try:
            conn.execute(_TABLE.insert().values(**values))
        except IntegrityError:
            # Another Cloud Run instance may have generated the same question
            # at the same time. Keep the first successful explanation.
            existing = conn.execute(
                select(_TABLE).where(_TABLE.c.question_key == key)
            ).mappings().first()
            if existing:
                return dict(existing)
            raise
    return values
