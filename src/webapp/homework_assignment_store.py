"""Persistent, privacy-minimised homework assignment history.

The RAG collection is a shared content library.  This store records only which
library document IDs have been shown to a pseudonymous learner so concurrent
requests and multiple web workers do not repeatedly serve the same homework.
It deliberately stores no homework text, answers, names, emails or prompts.
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Sequence

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    delete,
    insert,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine

from .db import get_engine, normalise_database_url

_DEFAULT = Path(__file__).resolve().parents[2] / "data" / "homework_assignments.db"


class HomeworkAssignmentStore:
    """Claim unseen RAG documents atomically for one pseudonymous learner."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = normalise_database_url(
            database_url
            or os.getenv("ASSIGNMENT_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or f"sqlite+pysqlite:///{_DEFAULT}"
        )
        self.engine: Engine = get_engine(self.database_url)
        self.metadata = MetaData()
        self.table = Table(
            "homework_assignments",
            self.metadata,
            Column("id", String(80), primary_key=True),
            Column("learner_key", String(100), nullable=False, index=True),
            Column("doc_id", String(120), nullable=False, index=True),
            Column("subject", String(80), nullable=False, index=True),
            Column("year_group", Integer, nullable=False, index=True),
            Column("content_kind", String(30), nullable=False, default="primary"),
            Column("assigned_at", DateTime(timezone=True), nullable=False, index=True),
            UniqueConstraint("learner_key", "doc_id", name="uq_assignment_learner_doc"),
        )
        self.metadata.create_all(self.engine)

    @staticmethod
    def _clean(value: Any, max_length: int) -> str:
        return str(value or "").strip()[:max_length]

    def seen_doc_ids(
        self,
        learner_key: str,
        *,
        subject: Optional[str] = None,
        year_group: Optional[int] = None,
        content_kind: Optional[str] = None,
        limit: int = 5_000,
    ) -> set[str]:
        learner = self._clean(learner_key, 100)
        if not learner:
            return set()
        query = select(self.table.c.doc_id).where(self.table.c.learner_key == learner)
        if subject:
            query = query.where(self.table.c.subject == self._clean(subject, 80))
        if year_group is not None:
            query = query.where(self.table.c.year_group == int(year_group))
        if content_kind:
            query = query.where(self.table.c.content_kind == self._clean(content_kind, 30))
        query = query.order_by(self.table.c.assigned_at.desc()).limit(max(1, min(int(limit), 20_000)))
        with self.engine.begin() as conn:
            return set(conn.execute(query).scalars().all())

    def claim_first_unseen(
        self,
        learner_key: str,
        candidates: Sequence[str],
        *,
        subject: str,
        year_group: int,
        content_kind: str = "primary",
    ) -> Optional[str]:
        """Atomically claim the first candidate not already shown.

        A unique constraint resolves races between simultaneous requests.  If
        another worker claims a candidate first, this request tries the next.
        """
        learner = self._clean(learner_key, 100)
        clean_subject = self._clean(subject, 80)
        kind = self._clean(content_kind, 30) or "primary"
        if not learner or not clean_subject:
            return None

        unique_candidates = list(dict.fromkeys(self._clean(item, 120) for item in candidates if item))
        for doc_id in unique_candidates:
            try:
                with self.engine.begin() as conn:
                    conn.execute(
                        insert(self.table).values(
                            id=f"asg_{uuid.uuid4().hex}",
                            learner_key=learner,
                            doc_id=doc_id,
                            subject=clean_subject,
                            year_group=int(year_group),
                            content_kind=kind,
                            assigned_at=datetime.now(UTC),
                        )
                    )
                return doc_id
            except IntegrityError:
                continue
        return None

    def record(
        self,
        learner_key: str,
        doc_id: str,
        *,
        subject: str,
        year_group: int,
        content_kind: str = "primary",
    ) -> bool:
        return self.claim_first_unseen(
            learner_key,
            [doc_id],
            subject=subject,
            year_group=year_group,
            content_kind=content_kind,
        ) is not None

    def delete_learner(self, learner_key: str) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                delete(self.table).where(self.table.c.learner_key == self._clean(learner_key, 100))
            )
        return int(result.rowcount or 0)

    def purge_older_than(self, days: int = 730, *, limit: int = 10_000) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=max(30, min(int(days), 3650)))
        with self.engine.begin() as conn:
            ids = conn.execute(
                select(self.table.c.id)
                .where(self.table.c.assigned_at < cutoff)
                .limit(max(1, min(int(limit), 50_000)))
            ).scalars().all()
            if ids:
                conn.execute(delete(self.table).where(self.table.c.id.in_(ids)))
        return len(ids)


_store: Optional[HomeworkAssignmentStore] = None
_store_lock = threading.Lock()


def get_assignment_store() -> HomeworkAssignmentStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = HomeworkAssignmentStore()
    return _store
