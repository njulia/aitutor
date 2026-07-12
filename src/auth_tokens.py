"""Random, revocable login sessions.

The cookie contains only a random token. The parent email remains server-side.
Production uses PostgreSQL through DATABASE_URL; SQLite is a local fallback.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, MetaData, String, Table, and_, create_engine, delete, insert, select, update

from src.webapp.db import engine_options, normalise_database_url

_DEFAULT = Path(__file__).resolve().parents[1] / "data" / "auth_sessions.db"
_MAX_AGE = max(900, min(int(os.getenv("SESSION_MAX_AGE", str(12 * 60 * 60))), 7 * 24 * 60 * 60))
_URL = normalise_database_url(os.getenv("AUTH_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite+pysqlite:///{_DEFAULT}")
_kwargs: Dict[str, Any] = engine_options(_URL)
_engine = create_engine(_URL, **_kwargs)
_metadata = MetaData()
_sessions = Table(
    "auth_sessions",
    _metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("username", String(254), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)
_metadata.create_all(_engine)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _clean(token: str) -> str:
    value = (token or "").strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value


def generate_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    with _engine.begin() as conn:
        conn.execute(
            insert(_sessions).values(
                token_hash=_hash(token),
                username=username.strip().lower(),
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(seconds=_MAX_AGE),
                revoked_at=None,
            )
        )
    return token


def verify_token(token: str) -> Optional[str]:
    value = _clean(token)
    if len(value) < 24:
        return None
    now = datetime.now(UTC)
    digest = _hash(value)
    with _engine.begin() as conn:
        row = conn.execute(
            select(_sessions).where(
                and_(
                    _sessions.c.token_hash == digest,
                    _sessions.c.revoked_at.is_(None),
                    _sessions.c.expires_at > now,
                )
            )
        ).first()
        if not row:
            return None
        conn.execute(
            update(_sessions).where(_sessions.c.token_hash == digest).values(last_seen_at=now)
        )
    return str(row._mapping["username"])


def revoke_token(token: str) -> bool:
    value = _clean(token)
    if not value:
        return False
    with _engine.begin() as conn:
        result = conn.execute(
            update(_sessions).where(_sessions.c.token_hash == _hash(value)).values(revoked_at=datetime.now(UTC))
        )
    return bool(result.rowcount)


def revoke_all_for_user(username: str) -> int:
    with _engine.begin() as conn:
        result = conn.execute(
            update(_sessions)
            .where(and_(_sessions.c.username == username.strip().lower(), _sessions.c.revoked_at.is_(None)))
            .values(revoked_at=datetime.now(UTC))
        )
    return int(result.rowcount or 0)


def purge_expired(limit: int = 5000) -> int:
    now = datetime.now(UTC)
    with _engine.begin() as conn:
        ids = conn.execute(
            select(_sessions.c.token_hash)
            .where(_sessions.c.expires_at <= now)
            .limit(max(1, min(limit, 20_000)))
        ).scalars().all()
        if ids:
            conn.execute(delete(_sessions).where(_sessions.c.token_hash.in_(ids)))
    return len(ids)
