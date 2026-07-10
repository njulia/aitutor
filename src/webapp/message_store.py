"""SQLite-backed message storage.

Only the minimum personal data needed for support is stored: user email,
message text, reply text, timestamps and delivery state.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Iterator, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "user_messages.db"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MessageStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or os.getenv("MESSAGE_DB_PATH", str(DEFAULT_DB_PATH)))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialise(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    access_token TEXT NOT NULL UNIQUE,
                    user_id TEXT,
                    user_email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS message_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    admin_name TEXT NOT NULL,
                    reply TEXT NOT NULL,
                    email_status TEXT NOT NULL DEFAULT 'not_requested',
                    email_error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(message_id) REFERENCES user_messages(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_user_messages_email
                    ON user_messages(user_email);
                CREATE INDEX IF NOT EXISTS idx_user_messages_status
                    ON user_messages(status);
                CREATE INDEX IF NOT EXISTS idx_message_replies_message
                    ON message_replies(message_id);
                """
            )

    def create_message(
        self,
        *,
        user_id: Optional[str],
        user_email: str,
        subject: str,
        category: str,
        message: str,
    ) -> dict[str, Any]:
        now = _now()
        token = secrets.token_urlsafe(24)
        with self._connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO user_messages
                    (access_token, user_id, user_email, subject, category, message, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (token, user_id, user_email.lower(), subject.strip(), category.strip(), message.strip(), now, now),
            )
            message_id = int(cur.lastrowid)
        return self.get_message(message_id, include_token=True)

    def get_message(self, message_id: int, *, include_token: bool = False) -> Optional[dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM user_messages WHERE id = ?", (message_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            replies = conn.execute(
                "SELECT * FROM message_replies WHERE message_id = ? ORDER BY id ASC",
                (message_id,),
            ).fetchall()
            result["replies"] = [dict(r) for r in replies]
        if not include_token:
            result.pop("access_token", None)
        return result

    def list_for_user(self, *, email: str, access_token: Optional[str] = None) -> list[dict[str, Any]]:
        with self._connection() as conn:
            if access_token:
                rows = conn.execute(
                    "SELECT id FROM user_messages WHERE user_email = ? OR access_token = ? ORDER BY id DESC",
                    (email.lower(), access_token),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM user_messages WHERE user_email = ? ORDER BY id DESC",
                    (email.lower(),),
                ).fetchall()
        return [self.get_message(int(row["id"])) for row in rows]

    def get_for_user(
        self,
        message_id: int,
        *,
        email: Optional[str],
        access_token: Optional[str],
    ) -> Optional[dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT user_email, access_token FROM user_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
        if not row:
            return None
        email_matches = bool(email and row["user_email"].lower() == email.lower())
        token_matches = bool(access_token and secrets.compare_digest(row["access_token"], access_token))
        return self.get_message(message_id) if email_matches or token_matches else None

    def list_admin(self, *, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self._connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT id FROM user_messages WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM user_messages ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self.get_message(int(row["id"])) for row in rows]

    def add_reply(
        self,
        *,
        message_id: int,
        admin_name: str,
        reply: str,
        email_status: str,
        email_error: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if not self.get_message(message_id):
            return None
        now = _now()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO message_replies
                    (message_id, admin_name, reply, email_status, email_error, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, admin_name.strip(), reply.strip(), email_status, email_error, now),
            )
            conn.execute(
                "UPDATE user_messages SET status = 'replied', updated_at = ? WHERE id = ?",
                (now, message_id),
            )
        return self.get_message(message_id)

    def update_status(self, message_id: int, status: str) -> Optional[dict[str, Any]]:
        if not self.get_message(message_id):
            return None
        with self._connection() as conn:
            conn.execute(
                "UPDATE user_messages SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), message_id),
            )
        return self.get_message(message_id)
