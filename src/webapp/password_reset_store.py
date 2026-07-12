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
