"""Persistent, question-level explanations for 11+ Topic Mastery.

Explanations are shared across students because they are tied to the stable
question identity, not to a pupil's answer. No student answer is stored.
"""
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Text, UniqueConstraint, delete, inspect, select, text
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
    Column("mastery_level", Integer, nullable=True),
    Column("plan_week", Integer, nullable=True),
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
    _migrate_topic_mastery_explanation_store(engine)


def _migrate_topic_mastery_explanation_store(engine: Engine) -> None:
    """为已存在的表补充 plan_week 列并放宽 mastery_level 约束。

    ``create_all`` 不会修改已存在的表，而生产库早已建好该表，因此需要
    显式迁移：新增 ``plan_week`` 列，并去掉 ``mastery_level`` 的 NOT NULL
    约束（52 周计划的讲解不携带 mastery_level）。
    """
    table_name = "elevenplus_topic_mastery_explanations"
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns(table_name)}
    with engine.begin() as conn:
        if "plan_week" not in existing:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN plan_week INTEGER"))
        if engine.dialect.name == "postgresql":
            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN mastery_level DROP NOT NULL"))


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


def year_round_question_key(
    *,
    doc_id: str,
    subject: str,
    topic: str,
    plan_week: int,
    question_index: int,
    question: str,
) -> str:
    canonical = " ".join(str(question or "").split()).casefold()
    raw = "|".join([
        str(doc_id or ""),
        str(subject or ""),
        str(topic or ""),
        str(plan_week),
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
    mastery_level: Optional[int],
    question_index: int,
    explanation: str,
    model_used: Optional[str],
    plan_week: Optional[int] = None,
) -> dict:
    init_topic_mastery_explanation_store()
    now = datetime.now(UTC)
    engine = _engine()
    values = {
        "question_key": key,
        "doc_id": str(doc_id),
        "subject": str(subject),
        "topic": str(topic),
        "mastery_level": mastery_level,
        "plan_week": plan_week,
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


def list_explanations(*, limit: int = 1000, offset: int = 0) -> List[dict]:
    """分页列出所有已保存的题目讲解（含 topic mastery 与 year round）。"""
    init_topic_mastery_explanation_store()
    with _engine().connect() as conn:
        rows = conn.execute(
            select(_TABLE)
            .order_by(_TABLE.c.updated_at.desc(), _TABLE.c.id.desc())
            .offset(max(0, int(offset)))
            .limit(max(1, min(int(limit), 1000)))
        ).mappings().all()
    return [dict(row) for row in rows]


def delete_explanations(keys: List[str]) -> int:
    """按 question_key 批量删除讲解，返回删除条数。"""
    clean = [str(key) for key in keys if str(key).strip()]
    if not clean:
        return 0
    init_topic_mastery_explanation_store()
    with _engine().begin() as conn:
        result = conn.execute(
            delete(_TABLE).where(_TABLE.c.question_key.in_(clean))
        )
    return int(result.rowcount or 0)
