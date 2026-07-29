"""First-party, aggregate-only product and marketing metrics.

The tables in this module deliberately contain no account, learner, email,
cookie, IP-address, answer, score, school or free-text fields.  Metrics are
coarse daily counters used to understand whether parent-facing journeys work.
They are never sent to advertising platforms or AI/embedding providers.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .db import get_engine, normalise_database_url

logger = logging.getLogger(__name__)

MARKETING_EVENTS = frozenset(
    {
        "landing_page_visit",
        "parent_account_created",
        "first_activity_completed",
        "return_within_7_days",
        "beta_access_started",
        "five_day_pass_purchased",
        "monthly_subscription_started",
        "subscription_cancelled",
    }
)
MARKETING_SOURCES = frozenset(
    {
        "direct",
        "organic",
        "whatsapp",
        "facebook",
        "google_ads",
        "email",
        "community",
        "referral",
        "unknown",
    }
)
MARKETING_PAGES = frozenset(
    {
        "home",
        "pricing",
        "register",
        "learning_app",
        "year3_maths",
        "year3_english",
        "elevenplus_calm",
        "beta",
        "other",
    }
)
VOICE_EVENTS = frozenset({"tts_used", "stt_used"})
VOICE_SUBJECTS = frozenset(
    {
        "Maths",
        "English",
        "Science",
        "History",
        "Geography",
        "French",
        "Spanish",
        "Chinese",
        "Verbal Reasoning",
        "Non-Verbal Reasoning",
        "Other",
    }
)

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "privacy_metrics.db"
_STORE: Optional["PrivacyMetricsStore"] = None
_STORE_LOCK = threading.Lock()


def _env_true(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_days(value: int, default: int = 180) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, 730))


class PrivacyMetricsStore:
    """Persist only aggregate daily counters with allow-listed dimensions."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        configured = (
            database_url
            or os.getenv("METRICS_DATABASE_URL")
            or os.getenv("DATABASE_URL")
        )
        if configured:
            url = normalise_database_url(configured)
        else:
            _DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite+pysqlite:///{_DEFAULT_DB_PATH}"
        self.engine: Engine = get_engine(url)
        self.metadata = MetaData()
        self.marketing = Table(
            "aggregate_marketing_metrics",
            self.metadata,
            Column("event_day", Date, nullable=False),
            Column("event_name", String(50), nullable=False),
            Column("source", String(30), nullable=False),
            Column("page", String(40), nullable=False),
            Column("event_count", Integer, nullable=False, default=0),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint(
                "event_day",
                "event_name",
                "source",
                "page",
                name="uq_aggregate_marketing_metric",
            ),
        )
        self.voice = Table(
            "aggregate_voice_metrics",
            self.metadata,
            Column("event_day", Date, nullable=False),
            Column("event_type", String(20), nullable=False),
            Column("year_group", Integer, nullable=False),
            Column("subject", String(40), nullable=False),
            Column("event_count", Integer, nullable=False, default=0),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint(
                "event_day",
                "event_type",
                "year_group",
                "subject",
                name="uq_aggregate_voice_metric",
            ),
        )
        self.metadata.create_all(self.engine)

    def _increment(self, table: Table, values: dict[str, Any]) -> None:
        key_columns = {
            key: value
            for key, value in values.items()
            if key not in {"event_count", "updated_at"}
        }
        condition = and_(
            *(table.c[key] == value for key, value in key_columns.items())
        )
        now = datetime.now(UTC)
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    update(table)
                    .where(condition)
                    .values(
                        event_count=table.c.event_count + 1,
                        updated_at=now,
                    )
                )
                if not result.rowcount:
                    conn.execute(
                        insert(table).values(
                            **key_columns,
                            event_count=1,
                            updated_at=now,
                        )
                    )
        except IntegrityError:
            # A second worker may have inserted the same aggregate bucket
            # between our UPDATE and INSERT. Increment that row once.
            with self.engine.begin() as conn:
                conn.execute(
                    update(table)
                    .where(condition)
                    .values(
                        event_count=table.c.event_count + 1,
                        updated_at=now,
                    )
                )

    def record_marketing(
        self,
        event_name: str,
        *,
        source: str = "unknown",
        page: str = "other",
        event_day: Optional[date] = None,
    ) -> bool:
        if event_name not in MARKETING_EVENTS:
            raise ValueError("Unsupported aggregate marketing event")
        if not _env_true("MARKETING_METRICS_ENABLED", False):
            return False
        safe_source = source if source in MARKETING_SOURCES else "unknown"
        safe_page = page if page in MARKETING_PAGES else "other"
        self._increment(
            self.marketing,
            {
                "event_day": event_day or datetime.now(UTC).date(),
                "event_name": event_name,
                "source": safe_source,
                "page": safe_page,
            },
        )
        return True

    def record_voice(
        self,
        event_type: str,
        *,
        year_group: int,
        subject: str,
        event_day: Optional[date] = None,
    ) -> bool:
        if event_type not in VOICE_EVENTS:
            raise ValueError("Unsupported voice event")
        if not _env_true("VOICE_METRICS_ENABLED", True):
            return False
        year = int(year_group)
        if year < 1 or year > 6:
            raise ValueError("Year group must be between 1 and 6")
        safe_subject = subject if subject in VOICE_SUBJECTS else "Other"
        self._increment(
            self.voice,
            {
                "event_day": event_day or datetime.now(UTC).date(),
                "event_type": event_type,
                "year_group": year,
                "subject": safe_subject,
            },
        )
        return True

    def marketing_summary(self, days: int = 180) -> dict[str, Any]:
        window = _bounded_days(days)
        cutoff = datetime.now(UTC).date() - timedelta(days=window - 1)
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.marketing.c.event_day,
                    self.marketing.c.event_name,
                    self.marketing.c.source,
                    self.marketing.c.page,
                    self.marketing.c.event_count,
                )
                .where(self.marketing.c.event_day >= cutoff)
                .order_by(
                    self.marketing.c.event_day,
                    self.marketing.c.event_name,
                    self.marketing.c.source,
                    self.marketing.c.page,
                )
            ).all()
            totals = conn.execute(
                select(
                    self.marketing.c.event_name,
                    func.sum(self.marketing.c.event_count).label("event_count"),
                )
                .where(self.marketing.c.event_day >= cutoff)
                .group_by(self.marketing.c.event_name)
                .order_by(self.marketing.c.event_name)
            ).all()
        return {
            "enabled": _env_true("MARKETING_METRICS_ENABLED", False),
            "aggregate_only": True,
            "window_days": window,
            "totals": {
                str(row.event_name): int(row.event_count or 0) for row in totals
            },
            "daily": [
                {
                    "day": row.event_day.isoformat(),
                    "event": row.event_name,
                    "source": row.source,
                    "page": row.page,
                    "count": int(row.event_count or 0),
                }
                for row in rows
            ],
        }

    def voice_summary(self, days: int = 180) -> dict[str, Any]:
        window = _bounded_days(days)
        cutoff = datetime.now(UTC).date() - timedelta(days=window - 1)
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.voice.c.event_type,
                    self.voice.c.year_group,
                    self.voice.c.subject,
                    func.sum(self.voice.c.event_count).label("event_count"),
                )
                .where(self.voice.c.event_day >= cutoff)
                .group_by(
                    self.voice.c.event_type,
                    self.voice.c.year_group,
                    self.voice.c.subject,
                )
                .order_by(
                    self.voice.c.event_type,
                    self.voice.c.year_group,
                    self.voice.c.subject,
                )
            ).all()
        by_age: dict[int, int] = {}
        by_subject: dict[str, int] = {}
        by_event_type: dict[str, int] = {}
        total = 0
        for row in rows:
            count = int(row.event_count or 0)
            total += count
            age = int(row.year_group) + 4
            by_age[age] = by_age.get(age, 0) + count
            by_subject[row.subject] = by_subject.get(row.subject, 0) + count
            by_event_type[row.event_type] = (
                by_event_type.get(row.event_type, 0) + count
            )
        return {
            "aggregate_only": True,
            "window_days": window,
            "total_events": total,
            "by_age": by_age,
            "by_subject": by_subject,
            "by_event_type": by_event_type,
        }


def get_privacy_metrics_store() -> PrivacyMetricsStore:
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = PrivacyMetricsStore()
    return _STORE


def record_marketing_event(
    event_name: str,
    *,
    source: str = "unknown",
    page: str = "other",
) -> bool:
    if not _env_true("MARKETING_METRICS_ENABLED", False):
        return False
    try:
        return get_privacy_metrics_store().record_marketing(
            event_name,
            source=source,
            page=page,
        )
    except Exception:
        # Measurement must never break registration, learning or billing.
        logger.exception("Could not update an aggregate marketing counter")
        return False


def record_voice_event(
    event_type: str,
    *,
    year_group: int,
    subject: str,
) -> bool:
    return get_privacy_metrics_store().record_voice(
        event_type,
        year_group=year_group,
        subject=subject,
    )


def marketing_summary(days: int = 180) -> dict[str, Any]:
    return get_privacy_metrics_store().marketing_summary(days)


def voice_summary(days: int = 180) -> dict[str, Any]:
    return get_privacy_metrics_store().voice_summary(days)
