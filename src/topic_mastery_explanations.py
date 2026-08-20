"""Persistent per-question explanations for 11+ Topic Mastery."""
from __future__ import annotations

import hashlib
import os
from typing import Optional

from sqlalchemy import text

from src.webapp.db import get_engine


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _engine():
    url = _database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return get_engine(url)


def init_topic_mastery_explanations_db() -> None:
    engine = _engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS elevenplus_topic_mastery_explanations (
                cache_key VARCHAR(128) PRIMARY KEY,
                doc_id TEXT NOT NULL,
                question_index INTEGER NOT NULL,
                model_used TEXT NOT NULL,
                explanation TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))


def explanation_key(doc_id: str, question_index: int, model_used: str) -> str:
    raw = f"topic_mastery|{doc_id}|{question_index}|{model_used}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_explanation(doc_id: str, question_index: int, model_used: str) -> Optional[str]:
    init_topic_mastery_explanations_db()
    key = explanation_key(doc_id, question_index, model_used)
    engine = _engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT explanation FROM elevenplus_topic_mastery_explanations WHERE cache_key = :key"),
            {"key": key},
        ).fetchone()
    return str(row[0]) if row and row[0] else None


def save_explanation(doc_id: str, question_index: int, model_used: str, explanation: str) -> None:
    if not explanation.strip():
        return
    init_topic_mastery_explanations_db()
    key = explanation_key(doc_id, question_index, model_used)
    engine = _engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO elevenplus_topic_mastery_explanations
                (cache_key, doc_id, question_index, model_used, explanation)
            VALUES (:key, :doc_id, :question_index, :model_used, :explanation)
            ON CONFLICT (cache_key) DO UPDATE SET
                explanation = EXCLUDED.explanation,
                updated_at = CURRENT_TIMESTAMP
        """), {
            "key": key,
            "doc_id": doc_id,
            "question_index": question_index,
            "model_used": model_used,
            "explanation": explanation.strip(),
        })
