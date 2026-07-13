"""Owner-bound tutor sessions backed by PostgreSQL (SQLite for local tests)."""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, and_, create_engine, delete, insert, select, update
from sqlalchemy.engine import Engine

from .db import engine_options, normalise_database_url

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "tutor_sessions.db"


class SessionTooLarge(ValueError):
    pass


class TutorSessionStore:
    def __init__(
        self,
        db_path: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        max_payload_bytes: int = 256 * 1024,
        database_url: Optional[str] = None,
    ) -> None:
        if database_url:
            self.database_url = normalise_database_url(database_url)
        elif db_path:
            self.database_url = normalise_database_url(db_path) if "://" in db_path else f"sqlite+pysqlite:///{db_path}"
        else:
            self.database_url = normalise_database_url(
                os.getenv("SESSION_DATABASE_URL")
                or os.getenv("DATABASE_URL")
                or f"sqlite+pysqlite:///{DEFAULT_DB_PATH}"
            )
        self.ttl_seconds = ttl_seconds or int(os.getenv("SESSION_TTL_SECONDS", "43200"))
        self.max_payload_bytes = max_payload_bytes
        kwargs: Dict[str, Any] = engine_options(self.database_url)
        self.engine: Engine = create_engine(self.database_url, **kwargs)
        self.metadata = MetaData()
        self.table = Table(
            "tutor_sessions",
            self.metadata,
            Column("session_id", String(80), primary_key=True),
            Column("owner_key", String(80), nullable=False, index=True),
            Column("payload_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
            Column("version", Integer, nullable=False, default=1),
        )
        self.metadata.create_all(self.engine)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def initialise(self) -> None:
        self.metadata.create_all(self.engine)

    def _encode(self, payload: Dict[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        size = len(encoded.encode("utf-8"))
        if size > self.max_payload_bytes:
            raise SessionTooLarge(f"Session payload is {size} bytes; limit is {self.max_payload_bytes} bytes")
        return encoded

    @staticmethod
    def _decode(row: Any) -> Dict[str, Any]:
        data = dict(row._mapping)
        payload = json.loads(data["payload_json"])
        payload.update({key: data[key] for key in ("session_id", "created_at", "updated_at", "expires_at", "version")})
        for key in ("created_at", "updated_at", "expires_at"):
            if hasattr(payload[key], "isoformat"):
                payload[key] = payload[key].isoformat()
        return payload

    def create(self, owner_key: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now = self._now()
        session_id = f"tut_{uuid.uuid4().hex}"
        values = dict(
            session_id=session_id,
            owner_key=owner_key,
            payload_json=self._encode(dict(payload or {})),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
            version=1,
        )
        with self.engine.begin() as conn:
            conn.execute(insert(self.table).values(**values))
            row = conn.execute(select(self.table).where(self.table.c.session_id == session_id)).first()
        return self._decode(row)

    def get(self, session_id: str, owner_key: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.table).where(
                    and_(
                        self.table.c.session_id == session_id,
                        self.table.c.owner_key == owner_key,
                        self.table.c.expires_at > self._now(),
                    )
                )
            ).first()
        return self._decode(row) if row else None

    def update(
        self,
        session_id: str,
        owner_key: str,
        updates: Dict[str, Any],
        *,
        expected_version: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        # Optimistic retry preserves concurrent updates across workers.
        for _attempt in range(20):
            now = self._now()
            with self.engine.begin() as conn:
                row = conn.execute(
                    select(self.table).where(
                        and_(
                            self.table.c.session_id == session_id,
                            self.table.c.owner_key == owner_key,
                            self.table.c.expires_at > now,
                        )
                    )
                ).first()
                if not row:
                    return None
                current = dict(row._mapping)
                if expected_version is not None and current["version"] != expected_version:
                    raise RuntimeError("Session was changed by another request")
                payload = json.loads(current["payload_json"])
                payload.update(updates)
                result = conn.execute(
                    update(self.table)
                    .where(
                        and_(
                            self.table.c.session_id == session_id,
                            self.table.c.owner_key == owner_key,
                            self.table.c.version == current["version"],
                        )
                    )
                    .values(
                        payload_json=self._encode(payload),
                        updated_at=now,
                        expires_at=now + timedelta(seconds=self.ttl_seconds),
                        version=current["version"] + 1,
                    )
                )
                if result.rowcount:
                    updated = conn.execute(select(self.table).where(self.table.c.session_id == session_id)).first()
                    return self._decode(updated)
        raise RuntimeError("Session was changed by too many concurrent requests")

    def claim(self, session_id: str, from_owner_key: str, to_owner_key: str) -> Optional[Dict[str, Any]]:
        """Move a short-lived anonymous session to the signed-in account owner.

        The caller must know the session ID and still possess the anonymous
        cookie that created it. This supports returning to generated homework
        after login without putting the homework into a URL or browser storage.
        """
        if not session_id or not from_owner_key or not to_owner_key:
            return None
        now = self._now()
        with self.engine.begin() as conn:
            result = conn.execute(
                update(self.table)
                .where(
                    and_(
                        self.table.c.session_id == session_id,
                        self.table.c.owner_key == from_owner_key,
                        self.table.c.expires_at > now,
                    )
                )
                .values(
                    owner_key=to_owner_key,
                    updated_at=now,
                    expires_at=now + timedelta(seconds=self.ttl_seconds),
                    version=self.table.c.version + 1,
                )
            )
            if not result.rowcount:
                row = conn.execute(
                    select(self.table).where(
                        and_(
                            self.table.c.session_id == session_id,
                            self.table.c.owner_key == to_owner_key,
                            self.table.c.expires_at > now,
                        )
                    )
                ).first()
                return self._decode(row) if row else None
            row = conn.execute(
                select(self.table).where(self.table.c.session_id == session_id)
            ).first()
        return self._decode(row) if row else None

    def delete(self, session_id: str, owner_key: str) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(
                delete(self.table).where(
                    and_(self.table.c.session_id == session_id, self.table.c.owner_key == owner_key)
                )
            )
        return bool(result.rowcount)

    def delete_owner(self, owner_key: str) -> int:
        """Erase all temporary tutor sessions belonging to one pseudonymous owner."""
        with self.engine.begin() as conn:
            result = conn.execute(delete(self.table).where(self.table.c.owner_key == owner_key))
        return int(result.rowcount or 0)

    def purge_expired(self, *, limit: int = 1000) -> int:
        with self.engine.begin() as conn:
            ids = conn.execute(
                select(self.table.c.session_id)
                .where(self.table.c.expires_at <= self._now())
                .limit(max(1, min(limit, 10_000)))
            ).scalars().all()
            if ids:
                conn.execute(delete(self.table).where(self.table.c.session_id.in_(ids)))
        return len(ids)
