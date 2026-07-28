"""Privacy-first learning memory for the AI tutor.

Only structured educational signals are stored. Raw questions, answers, images,
chat transcripts, names, schools and locations are deliberately excluded.
The store is PostgreSQL-ready through ``DATABASE_URL`` and uses SQLite only as
a local-development/test fallback.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .db import get_engine, normalise_database_url

_DEFAULT_SQLITE = Path(__file__).resolve().parents[2] / "data" / "learning_memory.db"
_ALLOWED_STYLES = {"short_steps", "worked_example", "gentle_hints", "visual_words"}
_ALLOWED_HINTS = {"one_at_a_time", "small_hint", "show_method_after_try"}
_TOPIC_CLEAN = re.compile(r"[^A-Za-z0-9+ &'()\-/]")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _database_url() -> str:
    return normalise_database_url(os.getenv("MEMORY_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite+pysqlite:///{_DEFAULT_SQLITE}")


def _engine(url: str) -> Engine:
    return get_engine(url)


def normalise_topic(value: Optional[str], subject: str = "General") -> str:
    topic = " ".join(str(value or "").split())
    topic = _TOPIC_CLEAN.sub("", topic)[:80].strip(" -/")
    return topic or f"{subject} general practice"


def infer_topic(subject: str, homework_text: str = "", explicit_topic: Optional[str] = None) -> str:
    if explicit_topic:
        return normalise_topic(explicit_topic, subject)
    text = f"{subject} {homework_text}".casefold()
    rules = [
        (("fraction", "numerator", "denominator"), "Fractions"),
        (("decimal",), "Decimals"),
        (("percentage", "percent"), "Percentages"),
        (("multiply", "multiplication", "times table", "×"), "Multiplication"),
        (("divide", "division", "÷"), "Division"),
        (("addition", " add ", "+"), "Addition"),
        (("subtract", "subtraction", "−"), "Subtraction"),
        (("shape", "angle", "perimeter", "area"), "Geometry and measures"),
        (("grammar", "punctuation", "sentence"), "Grammar and punctuation"),
        (("spelling",), "Spelling"),
        (("comprehension", "passage", "read the"), "Reading comprehension"),
        (("verbal reasoning",), "Verbal reasoning"),
        (("non-verbal", "non verbal"), "Non-verbal reasoning"),
    ]
    for needles, topic in rules:
        if any(needle in text for needle in needles):
            return topic
    return normalise_topic(None, subject)


def infer_misconception(review_text: str, score_ratio: Optional[float]) -> Optional[str]:
    if score_ratio is not None and score_ratio >= 0.85:
        return None
    text = str(review_text or "").casefold()
    rules = [
        (("denominator", "add the denominators"), "fraction_denominator_confusion"),
        (("place value",), "place_value_confusion"),
        (("sign", "positive", "negative"), "operation_sign_error"),
        (("units", "unit"), "missing_or_wrong_units"),
        (("punctuation",), "punctuation_error"),
        (("spelling",), "spelling_pattern_error"),
        (("evidence", "from the text"), "reading_evidence_missing"),
    ]
    for needles, code in rules:
        if any(needle in text for needle in needles):
            return code
    return "needs_more_practice" if score_ratio is not None and score_ratio < 0.7 else None


class LearningMemoryStore:
    """Structured memory with parent-controlled settings and retention."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or _database_url()
        self.engine = _engine(self.database_url)
        self.metadata = MetaData()
        self.settings = Table(
            "learning_memory_settings",
            self.metadata,
            # IDs are pseudonymous application IDs, never names/emails.
            Column("student_id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("enabled", Boolean, nullable=False, default=False),
            Column("retention_days", Integer, nullable=False, default=365),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            Column("enabled_at", DateTime(timezone=True), nullable=True),
            Column("consent_version", String(32), nullable=False, default="2026-07"),
        )
        self.preferences = Table(
            "learner_memory_preferences",
            self.metadata,
            Column("student_id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("explanation_style", String(40), nullable=False, default="short_steps"),
            Column("hint_style", String(40), nullable=False, default="one_at_a_time"),
            Column("accessibility", JSON, nullable=False, default=dict),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.events = Table(
            "learning_memory_events",
            self.metadata,
            Column("id", String(80), primary_key=True),
            Column("student_id", String(80), nullable=False, index=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("subject", String(80), nullable=False),
            Column("topic", String(80), nullable=False),
            Column("outcome", Float, nullable=False),
            Column("attempted", Integer, nullable=False, default=1),
            Column("correct_count", Integer, nullable=True),
            Column("difficulty", Integer, nullable=True),
            Column("misconception_code", String(80), nullable=True),
            Column("source", String(40), nullable=False, default="homework_review"),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
            Column("metadata_json", JSON, nullable=False, default=dict),
        )
        self.mastery = Table(
            "learning_mastery_state",
            self.metadata,
            Column("student_id", String(80), nullable=False),
            Column("account_id", String(80), nullable=False, index=True),
            Column("subject", String(80), nullable=False),
            Column("topic", String(80), nullable=False),
            Column("mastery_score", Float, nullable=False),
            Column("attempts", Integer, nullable=False),
            Column("correct_count", Integer, nullable=False),
            Column("last_practised_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint("student_id", "subject", "topic", name="uq_memory_mastery_topic"),
        )
        Index("idx_memory_events_student_created", self.events.c.student_id, self.events.c.created_at)
        Index("idx_memory_mastery_student_score", self.mastery.c.student_id, self.mastery.c.mastery_score)
        self.metadata.create_all(self.engine)

    @staticmethod
    def _row(row: Any) -> Optional[Dict[str, Any]]:
        return dict(row._mapping) if row is not None else None

    def get_settings(self, student_id: str, account_id: str, *, create: bool = True) -> Dict[str, Any]:
        def read():
            with self.engine.begin() as conn:
                return conn.execute(
                    select(self.settings).where(
                        and_(self.settings.c.student_id == student_id, self.settings.c.account_id == account_id)
                    )
                ).first()

        row = read()
        if row is None and create:
            now = _utcnow()
            try:
                with self.engine.begin() as conn:
                    conn.execute(
                        insert(self.settings).values(
                            student_id=student_id, account_id=account_id, enabled=False,
                            retention_days=365, updated_at=now, enabled_at=None,
                            consent_version="2026-07",
                        )
                    )
            except IntegrityError:
                # Another worker created the consent row first.
                pass
            row = read()
        return self._row(row) or {
            "student_id": student_id, "account_id": account_id,
            "enabled": False, "retention_days": 365,
        }

    def update_settings(
        self, student_id: str, account_id: str, *, enabled: bool, retention_days: int = 365
    ) -> Dict[str, Any]:
        retention = max(30, min(int(retention_days), 730))
        current = self.get_settings(student_id, account_id)
        now = _utcnow()
        with self.engine.begin() as conn:
            conn.execute(
                update(self.settings)
                .where(
                    and_(self.settings.c.student_id == student_id, self.settings.c.account_id == account_id)
                )
                .values(
                    enabled=bool(enabled),
                    retention_days=retention,
                    updated_at=now,
                    enabled_at=(now if enabled and not current.get("enabled") else current.get("enabled_at")),
                    consent_version="2026-07",
                )
            )
        if not enabled:
            # Disabling memory stops future collection. Existing records remain
            # visible so the parent can export or delete them explicitly.
            pass
        return self.get_settings(student_id, account_id)

    def get_preferences(self, student_id: str, account_id: str) -> Dict[str, Any]:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.preferences).where(
                    and_(self.preferences.c.student_id == student_id, self.preferences.c.account_id == account_id)
                )
            ).first()
        return self._row(row) or {
            "student_id": student_id,
            "account_id": account_id,
            "explanation_style": "short_steps",
            "hint_style": "one_at_a_time",
            "accessibility": {},
        }

    def update_preferences(
        self,
        student_id: str,
        account_id: str,
        *,
        explanation_style: str,
        hint_style: str,
        accessibility: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        explanation = explanation_style if explanation_style in _ALLOWED_STYLES else "short_steps"
        hints = hint_style if hint_style in _ALLOWED_HINTS else "one_at_a_time"
        allowed_accessibility = {
            key: bool(value)
            for key, value in (accessibility or {}).items()
            if key in {"larger_text", "reduced_motion", "high_contrast", "read_aloud"}
        }
        now = _utcnow()
        values = dict(
            student_id=student_id,
            account_id=account_id,
            explanation_style=explanation,
            hint_style=hints,
            accessibility=allowed_accessibility,
            updated_at=now,
        )
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(self.preferences.c.student_id).where(self.preferences.c.student_id == student_id)
            ).first()
            if existing:
                conn.execute(
                    update(self.preferences)
                    .where(
                        and_(self.preferences.c.student_id == student_id, self.preferences.c.account_id == account_id)
                    )
                    .values(**{key: value for key, value in values.items() if key not in {"student_id", "account_id"}})
                )
            else:
                conn.execute(insert(self.preferences).values(**values))
        return self.get_preferences(student_id, account_id)

    def record_event(
        self,
        *,
        student_id: str,
        account_id: str,
        subject: str,
        topic: str,
        outcome: float,
        attempted: int = 1,
        correct_count: Optional[int] = None,
        difficulty: Optional[int] = None,
        misconception_code: Optional[str] = None,
        source: str = "homework_review",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        settings = self.get_settings(student_id, account_id)
        if not settings.get("enabled"):
            return False
        now = _utcnow()
        attempted = max(1, min(int(attempted or 1), 100))
        ratio = max(0.0, min(float(outcome), 1.0))
        correct = None if correct_count is None else max(0, min(int(correct_count), attempted))
        clean_subject = " ".join(str(subject or "General").split())[:80] or "General"
        clean_topic = normalise_topic(topic, clean_subject)
        clean_source = " ".join(str(source or "homework_review").split())[:40]
        safe_metadata = {
            key: value
            for key, value in (metadata or {}).items()
            if key in {"mode", "from_rag", "question_count", "year_group"}
            and isinstance(value, (str, int, float, bool, type(None)))
        }
        expires = now + timedelta(days=int(settings["retention_days"]))
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.events).values(
                    id=f"mem_{uuid.uuid4().hex}",
                    student_id=student_id,
                    account_id=account_id,
                    subject=clean_subject,
                    topic=clean_topic,
                    outcome=ratio,
                    attempted=attempted,
                    correct_count=correct,
                    difficulty=(max(1, min(int(difficulty), 5)) if difficulty is not None else None),
                    misconception_code=(str(misconception_code)[:80] if misconception_code else None),
                    source=clean_source,
                    created_at=now,
                    expires_at=expires,
                    metadata_json=safe_metadata,
                )
            )
            row = conn.execute(
                select(self.mastery).where(
                    and_(
                        self.mastery.c.student_id == student_id,
                        self.mastery.c.account_id == account_id,
                        self.mastery.c.subject == clean_subject,
                        self.mastery.c.topic == clean_topic,
                    )
                )
            ).first()
            gained_correct = correct if correct is not None else round(ratio * attempted)
            if row:
                current = row._mapping
                total_attempts = int(current["attempts"]) + attempted
                total_correct = int(current["correct_count"]) + gained_correct
                # Recency-weighted score reacts to improvement while remaining stable.
                new_mastery = round(float(current["mastery_score"]) * 0.75 + ratio * 0.25, 4)
                conn.execute(
                    update(self.mastery)
                    .where(
                        and_(
                            self.mastery.c.student_id == student_id,
                            self.mastery.c.subject == clean_subject,
                            self.mastery.c.topic == clean_topic,
                        )
                    )
                    .values(
                        mastery_score=new_mastery,
                        attempts=total_attempts,
                        correct_count=total_correct,
                        last_practised_at=now,
                    )
                )
            else:
                conn.execute(
                    insert(self.mastery).values(
                        student_id=student_id,
                        account_id=account_id,
                        subject=clean_subject,
                        topic=clean_topic,
                        mastery_score=round(ratio, 4),
                        attempts=attempted,
                        correct_count=gained_correct,
                        last_practised_at=now,
                    )
                )
        return True

    def summary(self, student_id: str, account_id: str, *, recent_limit: int = 20) -> Dict[str, Any]:
        settings = self.get_settings(student_id, account_id)
        preferences = self.get_preferences(student_id, account_id)
        with self.engine.begin() as conn:
            mastery_rows = conn.execute(
                select(self.mastery)
                .where(
                    and_(self.mastery.c.student_id == student_id, self.mastery.c.account_id == account_id)
                )
                .order_by(self.mastery.c.mastery_score.asc(), self.mastery.c.last_practised_at.desc())
                .limit(50)
            ).all()
            event_rows = conn.execute(
                select(
                    self.events.c.id,
                    self.events.c.subject,
                    self.events.c.topic,
                    self.events.c.outcome,
                    self.events.c.attempted,
                    self.events.c.correct_count,
                    self.events.c.misconception_code,
                    self.events.c.source,
                    self.events.c.created_at,
                )
                .where(
                    and_(
                        self.events.c.student_id == student_id,
                        self.events.c.account_id == account_id,
                        self.events.c.expires_at > _utcnow(),
                    )
                )
                .order_by(self.events.c.created_at.desc())
                .limit(max(1, min(recent_limit, 100)))
            ).all()
        mastery = [dict(row._mapping) for row in mastery_rows]
        events = [dict(row._mapping) for row in event_rows]
        return {
            "settings": settings,
            "preferences": preferences,
            "weak_topics": mastery[:5],
            "strong_topics": sorted(mastery, key=lambda item: item["mastery_score"], reverse=True)[:5],
            "all_topics": mastery,
            "recent_events": events,
        }

    def prompt_context(self, student_id: str, account_id: str, *, max_chars: int = 700) -> str:
        summary = self.summary(student_id, account_id, recent_limit=5)
        if not summary["settings"].get("enabled"):
            return ""
        preferences = summary["preferences"]
        lines = [
            "Learning memory (structured, parent enabled):",
            f"Explanation style: {preferences['explanation_style']}; hint style: {preferences['hint_style']}.",
        ]
        if summary["weak_topics"]:
            weak = ", ".join(
                f"{item['subject']} – {item['topic']} ({round(item['mastery_score'] * 100)}%)"
                for item in summary["weak_topics"][:3]
            )
            lines.append(f"Topics needing practice: {weak}.")
        if summary["strong_topics"]:
            strong = ", ".join(
                f"{item['subject']} – {item['topic']}"
                for item in summary["strong_topics"][:2]
                if item["mastery_score"] >= 0.75
            )
            if strong:
                lines.append(f"Secure topics: {strong}.")
        context = " ".join(lines)
        return context[:max_chars]

    def delete_topic(self, student_id: str, account_id: str, subject: str, topic: str) -> int:
        clean_subject = " ".join(subject.split())[:80]
        clean_topic = normalise_topic(topic, clean_subject)
        with self.engine.begin() as conn:
            result = conn.execute(
                delete(self.events).where(
                    and_(
                        self.events.c.student_id == student_id,
                        self.events.c.account_id == account_id,
                        self.events.c.subject == clean_subject,
                        self.events.c.topic == clean_topic,
                    )
                )
            )
            conn.execute(
                delete(self.mastery).where(
                    and_(
                        self.mastery.c.student_id == student_id,
                        self.mastery.c.account_id == account_id,
                        self.mastery.c.subject == clean_subject,
                        self.mastery.c.topic == clean_topic,
                    )
                )
            )
        return int(result.rowcount or 0)

    def delete_all(self, student_id: str, account_id: str, *, include_preferences: bool = False) -> int:
        with self.engine.begin() as conn:
            events = conn.execute(
                delete(self.events).where(
                    and_(self.events.c.student_id == student_id, self.events.c.account_id == account_id)
                )
            )
            conn.execute(
                delete(self.mastery).where(
                    and_(self.mastery.c.student_id == student_id, self.mastery.c.account_id == account_id)
                )
            )
            if include_preferences:
                conn.execute(
                    delete(self.preferences).where(
                        and_(
                            self.preferences.c.student_id == student_id,
                            self.preferences.c.account_id == account_id,
                        )
                    )
                )
                conn.execute(
                    delete(self.settings).where(
                        and_(
                            self.settings.c.student_id == student_id,
                            self.settings.c.account_id == account_id,
                        )
                    )
                )
        return int(events.rowcount or 0)

    def export(self, student_id: str, account_id: str) -> Dict[str, Any]:
        data = self.summary(student_id, account_id, recent_limit=100)
        data["exported_at"] = _utcnow().isoformat()
        data["notice"] = "This export contains structured learning data only; raw conversations are not stored."
        return data

    def purge_expired(self, *, limit: int = 5000) -> int:
        now = _utcnow()
        with self.engine.begin() as conn:
            ids = conn.execute(
                select(self.events.c.id)
                .where(self.events.c.expires_at <= now)
                .limit(max(1, min(limit, 20_000)))
            ).scalars().all()
            if not ids:
                return 0
            conn.execute(delete(self.events).where(self.events.c.id.in_(ids)))
        return len(ids)


_store: Optional[LearningMemoryStore] = None


def get_memory_store() -> LearningMemoryStore:
    global _store
    if _store is None:
        _store = LearningMemoryStore()
    return _store
