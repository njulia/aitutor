"""Short-lived, single-use password reset tokens and privacy-safe rate limits."""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PasswordResetStore:
    """SQLite store for reset tokens.

    Raw reset tokens are never stored. Parent/guardian email addresses are kept
    only with short-lived reset records, then removed by retention cleanup.
    """

    def __init__(self, project_root: str, db_path: Optional[str] = None) -> None:
        configured = db_path or os.getenv("PASSWORD_RESET_DB_PATH")
        self.db_path = Path(configured) if configured else Path(project_root) / "data" / "password_resets.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_minutes = max(5, min(int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES") or "30"), 120))
        self.max_email_per_hour = max(1, int(os.getenv("PASSWORD_RESET_MAX_EMAIL_PER_HOUR") or "3"))
        self.max_client_per_hour = max(1, int(os.getenv("PASSWORD_RESET_MAX_CLIENT_PER_HOUR") or "10"))
        self._create_schema()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            yield conn
        finally:
            conn.close()

    def _create_schema(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id TEXT PRIMARY KEY,
                    account_email TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_password_reset_expiry
                    ON password_reset_tokens(expires_at);
                CREATE INDEX IF NOT EXISTS idx_password_reset_account
                    ON password_reset_tokens(account_email, created_at DESC);

                CREATE TABLE IF NOT EXISTS password_reset_requests (
                    id TEXT PRIMARY KEY,
                    email_hash TEXT NOT NULL,
                    client_hash TEXT NOT NULL,
                    requested_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_password_reset_request_email
                    ON password_reset_requests(email_hash, requested_at DESC);
                CREATE INDEX IF NOT EXISTS idx_password_reset_request_client
                    ON password_reset_requests(client_hash, requested_at DESC);
                """
            )

    def record_request_if_allowed(self, email: str, client_hash: str) -> bool:
        """Atomically check and record rate limits for every submitted email."""
        now = _now()
        cutoff = _iso(now - timedelta(hours=1))
        email_hash = _hash(email.strip().lower())
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM password_reset_requests WHERE requested_at < ?", (_iso(now - timedelta(days=1)),))
            email_count = conn.execute(
                "SELECT COUNT(*) FROM password_reset_requests WHERE email_hash = ? AND requested_at >= ?",
                (email_hash, cutoff),
            ).fetchone()[0]
            client_count = conn.execute(
                "SELECT COUNT(*) FROM password_reset_requests WHERE client_hash = ? AND requested_at >= ?",
                (client_hash, cutoff),
            ).fetchone()[0]
            if email_count >= self.max_email_per_hour or client_count >= self.max_client_per_hour:
                conn.execute("COMMIT")
                return False
            conn.execute(
                "INSERT INTO password_reset_requests (id, email_hash, client_hash, requested_at) VALUES (?, ?, ?, ?)",
                (f"prr_{uuid.uuid4().hex}", email_hash, client_hash, _iso(now)),
            )
            conn.execute("COMMIT")
            return True

    def create_token(self, account_email: str) -> tuple[str, datetime]:
        now = _now()
        expires_at = now + timedelta(minutes=self.token_minutes)
        token = secrets.token_urlsafe(48)
        token_hash = _hash(token)
        email = account_email.strip().lower()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # Only the newest link should work.
            conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE account_email = ? AND used_at IS NULL",
                (_iso(now), email),
            )
            conn.execute(
                """INSERT INTO password_reset_tokens
                   (id, account_email, token_hash, created_at, expires_at, used_at)
                   VALUES (?, ?, ?, ?, ?, NULL)""",
                (f"prt_{uuid.uuid4().hex}", email, token_hash, _iso(now), _iso(expires_at)),
            )
            conn.execute("COMMIT")
        return token, expires_at

    def is_valid(self, token: str) -> bool:
        if not token or len(token) > 512:
            return False
        now = _iso(_now())
        with self._connection() as conn:
            row = conn.execute(
                """SELECT 1 FROM password_reset_tokens
                   WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?""",
                (_hash(token), now),
            ).fetchone()
        return bool(row)

    def consume(self, token: str) -> Optional[str]:
        """Claim a valid token once and return its account email."""
        if not token or len(token) > 512:
            return None
        now = _now()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT id, account_email FROM password_reset_tokens
                   WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?""",
                (_hash(token), _iso(now)),
            ).fetchone()
            if not row:
                conn.execute("COMMIT")
                return None
            updated = conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
                (_iso(now), row["id"]),
            ).rowcount
            conn.execute("COMMIT")
        return row["account_email"] if updated == 1 else None

    def purge_expired(self) -> int:
        now = _now()
        token_cutoff = _iso(now - timedelta(days=1))
        request_cutoff = _iso(now - timedelta(days=1))
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            removed = conn.execute(
                "DELETE FROM password_reset_tokens WHERE expires_at < ? OR used_at IS NOT NULL",
                (token_cutoff,),
            ).rowcount
            conn.execute("DELETE FROM password_reset_requests WHERE requested_at < ?", (request_cutoff,))
            conn.execute("COMMIT")
        return int(removed or 0)

# Use the shared SQL database on hosted deployments; preserve explicit SQLite
# paths for local development and the migration-focused unit tests above.
_SQLitePasswordResetStore = PasswordResetStore


class _SQLPasswordResetStore:
    def __init__(self, database_url: str) -> None:
        from sqlalchemy import Column, DateTime, MetaData, String, Table, and_, delete, func, insert, select, update
        from .db import get_engine, normalise_database_url

        self._sa = {"and_": and_, "delete": delete, "func": func, "insert": insert, "select": select, "update": update}
        self.database_url = normalise_database_url(database_url)
        self.engine = get_engine(self.database_url)
        metadata = MetaData()
        self.tokens = Table(
            "password_reset_tokens", metadata,
            Column("id", String(80), primary_key=True),
            Column("account_email", String(320), nullable=False, index=True),
            Column("token_hash", String(64), nullable=False, unique=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
            Column("used_at", DateTime(timezone=True)),
        )
        self.requests = Table(
            "password_reset_requests", metadata,
            Column("id", String(80), primary_key=True),
            Column("email_hash", String(64), nullable=False, index=True),
            Column("client_hash", String(128), nullable=False, index=True),
            Column("requested_at", DateTime(timezone=True), nullable=False, index=True),
        )
        self.token_minutes = max(5, min(int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES") or "30"), 120))
        self.max_email_per_hour = max(1, min(int(os.getenv("PASSWORD_RESET_MAX_EMAIL_PER_HOUR") or "3"), 20))
        self.max_client_per_hour = max(1, min(int(os.getenv("PASSWORD_RESET_MAX_CLIENT_PER_HOUR") or "10"), 100))
        metadata.create_all(self.engine)

    def record_request_if_allowed(self, email: str, client_hash: str) -> bool:
        now = _now()
        cutoff = now - timedelta(hours=1)
        email_hash = _hash(email.strip().lower())
        select, func = self._sa["select"], self._sa["func"]
        with self.engine.begin() as conn:
            conn.execute(self._sa["delete"](self.requests).where(self.requests.c.requested_at < now - timedelta(days=1)))
            email_count = conn.execute(select(func.count()).where(self._sa["and_"](self.requests.c.email_hash == email_hash, self.requests.c.requested_at >= cutoff))).scalar_one()
            client_count = conn.execute(select(func.count()).where(self._sa["and_"](self.requests.c.client_hash == client_hash, self.requests.c.requested_at >= cutoff))).scalar_one()
            if email_count >= self.max_email_per_hour or client_count >= self.max_client_per_hour:
                return False
            conn.execute(self._sa["insert"](self.requests).values(id=f"prr_{uuid.uuid4().hex}", email_hash=email_hash, client_hash=client_hash, requested_at=now))
        return True

    def create_token(self, account_email: str) -> tuple[str, datetime]:
        now = _now()
        expires_at = now + timedelta(minutes=self.token_minutes)
        token = secrets.token_urlsafe(48)
        email = account_email.strip().lower()
        with self.engine.begin() as conn:
            conn.execute(self._sa["update"](self.tokens).where(self._sa["and_"](self.tokens.c.account_email == email, self.tokens.c.used_at.is_(None))).values(used_at=now))
            conn.execute(self._sa["insert"](self.tokens).values(id=f"prt_{uuid.uuid4().hex}", account_email=email, token_hash=_hash(token), created_at=now, expires_at=expires_at, used_at=None))
        return token, expires_at

    def is_valid(self, token: str) -> bool:
        if not token or len(token) > 512:
            return False
        with self.engine.begin() as conn:
            row = conn.execute(self._sa["select"](self.tokens.c.id).where(self._sa["and_"](self.tokens.c.token_hash == _hash(token), self.tokens.c.used_at.is_(None), self.tokens.c.expires_at > _now()))).first()
        return bool(row)

    def consume(self, token: str) -> Optional[str]:
        if not token or len(token) > 512:
            return None
        now = _now()
        with self.engine.begin() as conn:
            row = conn.execute(self._sa["select"](self.tokens.c.id, self.tokens.c.account_email).where(self._sa["and_"](self.tokens.c.token_hash == _hash(token), self.tokens.c.used_at.is_(None), self.tokens.c.expires_at > now))).first()
            if not row:
                return None
            result = conn.execute(self._sa["update"](self.tokens).where(self._sa["and_"](self.tokens.c.id == row.id, self.tokens.c.used_at.is_(None))).values(used_at=now))
        return str(row.account_email) if result.rowcount == 1 else None

    def purge_expired(self) -> int:
        now = _now()
        with self.engine.begin() as conn:
            removed = conn.execute(self._sa["delete"](self.tokens).where((self.tokens.c.expires_at < now - timedelta(days=1)) | self.tokens.c.used_at.is_not(None))).rowcount
            conn.execute(self._sa["delete"](self.requests).where(self.requests.c.requested_at < now - timedelta(days=1)))
        return int(removed or 0)


class PasswordResetStore:
    """Shared database store in production, explicit SQLite store in tests."""
    def __init__(self, project_root: str, db_path: Optional[str] = None) -> None:
        database_url = os.getenv("PASSWORD_RESET_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not db_path and database_url and not database_url.strip().lower().startswith("sqlite"):
            self._impl = _SQLPasswordResetStore(database_url)
        else:
            self._impl = _SQLitePasswordResetStore(project_root, db_path=db_path)

    def __getattr__(self, name: str):
        return getattr(self._impl, name)
