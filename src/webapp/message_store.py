"""SQLite storage for parent/guardian support messages."""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

VALID_STATUSES = {"open", "pending", "replied", "closed"}
VALID_CATEGORIES = {"general", "homework", "account", "billing", "privacy", "technical"}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MessageStore:
    def __init__(self, project_root: str, db_path: Optional[str] = None) -> None:
        configured = db_path or os.getenv("MESSAGE_DB_PATH")
        self.db_path = Path(configured) if configured else Path(project_root) / "data" / "messages.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = max(30, int(os.getenv("MESSAGE_RETENTION_DAYS") or "180"))
        self._create_schema()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            yield conn
        finally:
            conn.close()

    def _create_schema(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")

            # Check existing columns to handle migration
            cursor = conn.execute("PRAGMA table_info(support_messages)")
            columns = {row["name"] for row in cursor.fetchall()}

            if not columns:
                # Fresh install
                conn.executescript(
                    """
                    CREATE TABLE support_messages (
                        id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        contact_email TEXT,
                        category TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        message TEXT NOT NULL,
                        status TEXT NOT NULL,
                        access_token_hash TEXT NOT NULL,
                        user_read_at TEXT,
                        admin_read_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    );
                    """
                )
            else:
                # Migration: Add missing columns if they don't exist
                if "category" not in columns:
                    conn.execute("ALTER TABLE support_messages ADD COLUMN category TEXT NOT NULL DEFAULT 'general'")
                if "access_token_hash" not in columns:
                    conn.execute("ALTER TABLE support_messages ADD COLUMN access_token_hash TEXT NOT NULL DEFAULT ''")
                if "user_read_at" not in columns:
                    conn.execute("ALTER TABLE support_messages ADD COLUMN user_read_at TEXT")
                if "admin_read_at" not in columns:
                    conn.execute("ALTER TABLE support_messages ADD COLUMN admin_read_at TEXT")
                if "expires_at" not in columns:
                    default_expiry = _iso(_now() + timedelta(days=self.retention_days))
                    conn.execute(f"ALTER TABLE support_messages ADD COLUMN expires_at TEXT NOT NULL DEFAULT '{default_expiry}'")

                # FIX: Handle legacy 'access_token' column which might be NOT NULL without default
                if "access_token" in columns:
                    # We can't easily change NOT NULL in SQLite without table recreation.
                    # But we can check if it has a default. 
                    # For now, let's mark it as a legacy column we might need to fill.
                    self._has_legacy_token_column = True
                else:
                    self._has_legacy_token_column = False

            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_support_messages_owner
                    ON support_messages(owner_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_support_messages_status
                    ON support_messages(status, created_at DESC);

                CREATE TABLE IF NOT EXISTS support_replies (
                    id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    reply TEXT NOT NULL,
                    admin_email TEXT NOT NULL,
                    email_requested INTEGER NOT NULL DEFAULT 0,
                    email_status TEXT NOT NULL DEFAULT 'not_requested',
                    email_error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(message_id) REFERENCES support_messages(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_support_replies_message
                    ON support_replies(message_id, created_at ASC);
                """
            )

    @staticmethod
    def _message_dict(row: sqlite3.Row, *, include_private: bool = False) -> Dict[str, Any]:
        data = dict(row)
        data.pop("access_token_hash", None)
        if not include_private:
            data.pop("owner_id", None)
            data.pop("admin_read_at", None)
        return data

    @staticmethod
    def _reply_dict(row: sqlite3.Row, *, include_private: bool = False) -> Dict[str, Any]:
        data = dict(row)
        data["email_requested"] = bool(data.get("email_requested"))
        if not include_private:
            data.pop("admin_email", None)
            data.pop("email_error", None)
        return data

    def create_message(
        self,
        *,
        owner_id: str,
        contact_email: Optional[str],
        category: str,
        subject: str,
        message: str,
    ) -> Tuple[Dict[str, Any], str]:
        now = _now()
        message_id = f"msg_{uuid.uuid4().hex}"
        token = secrets.token_urlsafe(32)
        category = category if category in VALID_CATEGORIES else "general"
        record = {
            "id": message_id,
            "owner_id": owner_id,
            "contact_email": contact_email,
            "category": category,
            "subject": subject,
            "message": message,
            "status": "open",
            "access_token_hash": _token_hash(token),
            "user_read_at": _iso(now),
            "admin_read_at": None,
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "expires_at": _iso(now + timedelta(days=self.retention_days)),
        }
        if getattr(self, "_has_legacy_token_column", False):
            record["access_token"] = ""

        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            
            cols = list(record.keys())
            placeholders = ", ".join(f":{c}" for c in cols)
            col_names = ", ".join(cols)
            
            conn.execute(
                f"INSERT INTO support_messages ({col_names}) VALUES ({placeholders})",
                record,
            )
            conn.commit()
        return self.get_for_admin(message_id), token

    def _authorised_row(self, message_id: str, owner_id: str, access_token: Optional[str]) -> Optional[sqlite3.Row]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM support_messages WHERE id = ?", (message_id,)).fetchone()
        if not row:
            return None
        if row["owner_id"] == owner_id:
            return row
        if access_token and secrets.compare_digest(row["access_token_hash"], _token_hash(access_token)):
            return row
        return None

    def list_for_owner(self, owner_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT m.*,
                          (SELECT COUNT(*) FROM support_replies r WHERE r.message_id = m.id) AS reply_count,
                          (SELECT MAX(r.created_at) FROM support_replies r WHERE r.message_id = m.id) AS last_reply_at
                   FROM support_messages m
                   WHERE m.owner_id = ?
                   ORDER BY m.updated_at DESC LIMIT ?""",
                (owner_id, limit),
            ).fetchall()
        return [self._message_dict(row) for row in rows]

    def get_for_user(self, message_id: str, owner_id: str, access_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        row = self._authorised_row(message_id, owner_id, access_token)
        if not row:
            return None
        with self._connection() as conn:
            replies = conn.execute(
                "SELECT * FROM support_replies WHERE message_id = ? ORDER BY created_at ASC", (message_id,)
            ).fetchall()
        item = self._message_dict(row)
        item["replies"] = [self._reply_dict(reply) for reply in replies]
        return item

    def mark_user_read(self, message_id: str, owner_id: str, access_token: Optional[str] = None) -> bool:
        if not self._authorised_row(message_id, owner_id, access_token):
            return False
        with self._connection() as conn:
            result = conn.execute(
                "UPDATE support_messages SET user_read_at = ?, updated_at = updated_at WHERE id = ?",
                (_iso(_now()), message_id),
            )
        return bool(result.rowcount)

    def list_admin(
        self,
        *,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        if status in VALID_STATUSES:
            conditions.append("m.status = ?")
            params.append(status)
        if category in VALID_CATEGORIES:
            conditions.append("m.category = ?")
            params.append(category)
        if search:
            conditions.append("(LOWER(m.subject) LIKE ? OR LOWER(COALESCE(m.contact_email, '')) LIKE ?)")
            term = f"%{search.strip().lower()[:120]}%"
            params.extend([term, term])
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        params.extend([limit, offset])
        query = f"""
            SELECT m.*,
                   (SELECT COUNT(*) FROM support_replies r WHERE r.message_id = m.id) AS reply_count,
                   (SELECT MAX(r.created_at) FROM support_replies r WHERE r.message_id = m.id) AS last_reply_at
            FROM support_messages m
            {where}
            ORDER BY CASE WHEN m.admin_read_at IS NULL THEN 0 ELSE 1 END,
                     m.updated_at DESC
            LIMIT ? OFFSET ?
        """
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._message_dict(row, include_private=True) for row in rows]

    def get_for_admin(self, message_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM support_messages WHERE id = ?", (message_id,)).fetchone()
            if not row:
                return None
            replies = conn.execute(
                "SELECT * FROM support_replies WHERE message_id = ? ORDER BY created_at ASC", (message_id,)
            ).fetchall()
        item = self._message_dict(row, include_private=True)
        item["replies"] = [self._reply_dict(reply, include_private=True) for reply in replies]
        return item

    def mark_admin_read(self, message_id: str) -> bool:
        with self._connection() as conn:
            result = conn.execute(
                "UPDATE support_messages SET admin_read_at = COALESCE(admin_read_at, ?) WHERE id = ?",
                (_iso(_now()), message_id),
            )
        return bool(result.rowcount)

    def add_reply(
        self,
        *,
        message_id: str,
        reply: str,
        admin_email: str,
        email_requested: bool,
    ) -> Optional[Dict[str, Any]]:
        now = _now()
        reply_id = f"reply_{uuid.uuid4().hex}"
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT id FROM support_messages WHERE id = ?", (message_id,)).fetchone()
            if not existing:
                conn.rollback()
                return None
            conn.execute(
                """INSERT INTO support_replies
                   (id, message_id, reply, admin_email, email_requested, email_status, email_error, created_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', NULL, ?)""",
                (reply_id, message_id, reply, admin_email, int(email_requested), _iso(now)),
            )
            conn.execute(
                """UPDATE support_messages
                   SET status = 'replied', updated_at = ?, user_read_at = NULL, admin_read_at = COALESCE(admin_read_at, ?)
                   WHERE id = ?""",
                (_iso(now), _iso(now), message_id),
            )
            conn.commit()
        return self.get_reply(reply_id, include_private=True)

    def get_reply(self, reply_id: str, *, include_private: bool = False) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM support_replies WHERE id = ?", (reply_id,)).fetchone()
        return self._reply_dict(row, include_private=include_private) if row else None

    def update_reply_delivery(self, reply_id: str, status: str, error: Optional[str]) -> None:
        with self._connection() as conn:
            conn.execute(
                "UPDATE support_replies SET email_status = ?, email_error = ? WHERE id = ?",
                (status, error[:300] if error else None, reply_id),
            )

    def update_status(self, message_id: str, status: str) -> bool:
        if status not in VALID_STATUSES:
            return False
        with self._connection() as conn:
            result = conn.execute(
                "UPDATE support_messages SET status = ?, updated_at = ? WHERE id = ?",
                (status, _iso(_now()), message_id),
            )
        return bool(result.rowcount)

    def summary(self) -> Dict[str, int]:
        with self._connection() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS total FROM support_messages GROUP BY status").fetchall()
            unread = conn.execute(
                "SELECT COUNT(*) AS total FROM support_messages WHERE admin_read_at IS NULL"
            ).fetchone()["total"]
            total = conn.execute("SELECT COUNT(*) AS total FROM support_messages").fetchone()["total"]
        result = {status: 0 for status in VALID_STATUSES}
        result.update({row["status"]: int(row["total"]) for row in rows})
        result["unread"] = int(unread)
        result["total"] = int(total)
        return result

    def purge_expired(self) -> int:
        with self._connection() as conn:
            result = conn.execute("DELETE FROM support_messages WHERE expires_at < ?", (_iso(_now()),))
        return int(result.rowcount or 0)

    def delete_for_owners(self, owner_ids: Iterable[str]) -> int:
        clean = [str(value) for value in owner_ids if value]
        if not clean:
            return 0
        placeholders = ",".join("?" for _ in clean)
        with self._connection() as conn:
            result = conn.execute(f"DELETE FROM support_messages WHERE owner_id IN ({placeholders})", clean)
        return int(result.rowcount or 0)

# ---------------------------------------------------------------------------
# Production SQL store
# ---------------------------------------------------------------------------
# Keep the small SQLite implementation above for explicit local/test db_path
# use. In hosted production the public MessageStore wrapper below selects the
# shared SQLAlchemy/PostgreSQL database so messages survive instance restarts
# and are safe across multiple web workers.
_SQLiteMessageStore = MessageStore


class _SQLMessageStore:
    def __init__(self, database_url: str) -> None:
        from sqlalchemy import (
            Boolean, Column, DateTime, ForeignKey, MetaData, String, Table, Text,
            and_, case, delete, func, insert, or_, select, update,
        )
        from .db import get_engine, normalise_database_url

        self._sa = {
            "and_": and_, "case": case, "delete": delete, "func": func,
            "insert": insert, "or_": or_, "select": select, "update": update,
        }
        self.database_url = normalise_database_url(database_url)
        self.engine = get_engine(self.database_url)
        metadata = MetaData()
        self.messages = Table(
            "support_messages", metadata,
            Column("id", String(80), primary_key=True),
            Column("owner_id", String(160), nullable=False, index=True),
            Column("contact_email", String(320)),
            Column("category", String(40), nullable=False),
            Column("subject", String(200), nullable=False),
            Column("message", Text, nullable=False),
            Column("status", String(30), nullable=False, index=True),
            Column("access_token_hash", String(64), nullable=False),
            Column("user_read_at", DateTime(timezone=True)),
            Column("admin_read_at", DateTime(timezone=True)),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False, index=True),
            Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
        )
        self.replies = Table(
            "support_replies", metadata,
            Column("id", String(80), primary_key=True),
            Column("message_id", String(80), ForeignKey("support_messages.id", ondelete="CASCADE"), nullable=False, index=True),
            Column("reply", Text, nullable=False),
            Column("admin_email", String(320), nullable=False),
            Column("email_requested", Boolean, nullable=False, default=False),
            Column("email_status", String(40), nullable=False, default="not_requested"),
            Column("email_error", String(300)),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.retention_days = max(30, min(int(os.getenv("MESSAGE_RETENTION_DAYS") or "180"), 730))
        metadata.create_all(self.engine)

    @staticmethod
    def _serialise(data: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(data)
        for key, value in list(result.items()):
            if isinstance(value, datetime):
                result[key] = _iso(value)
        return result

    def _message_dict(self, row: Any, *, include_private: bool = False) -> Dict[str, Any]:
        data = self._serialise(dict(row._mapping if hasattr(row, "_mapping") else row))
        data.pop("access_token_hash", None)
        if not include_private:
            data.pop("owner_id", None)
            data.pop("admin_read_at", None)
        return data

    def _reply_dict(self, row: Any, *, include_private: bool = False) -> Dict[str, Any]:
        data = self._serialise(dict(row._mapping if hasattr(row, "_mapping") else row))
        data["email_requested"] = bool(data.get("email_requested"))
        if not include_private:
            data.pop("admin_email", None)
            data.pop("email_error", None)
        return data

    def _message_projection(self):
        select, func = self._sa["select"], self._sa["func"]
        reply_count = select(func.count()).where(self.replies.c.message_id == self.messages.c.id).scalar_subquery().label("reply_count")
        last_reply = select(func.max(self.replies.c.created_at)).where(self.replies.c.message_id == self.messages.c.id).scalar_subquery().label("last_reply_at")
        return [self.messages, reply_count, last_reply]

    def create_message(self, *, owner_id: str, contact_email: Optional[str], category: str, subject: str, message: str) -> Tuple[Dict[str, Any], str]:
        now = _now()
        message_id = f"msg_{uuid.uuid4().hex}"
        token = secrets.token_urlsafe(32)
        values = {
            "id": message_id, "owner_id": owner_id, "contact_email": contact_email,
            "category": category if category in VALID_CATEGORIES else "general",
            "subject": subject, "message": message, "status": "open",
            "access_token_hash": _token_hash(token), "user_read_at": now,
            "admin_read_at": None, "created_at": now, "updated_at": now,
            "expires_at": now + timedelta(days=self.retention_days),
        }
        with self.engine.begin() as conn:
            conn.execute(self._sa["insert"](self.messages).values(**values))
        return self.get_for_admin(message_id), token

    def _authorised_row(self, message_id: str, owner_id: str, access_token: Optional[str]):
        with self.engine.begin() as conn:
            row = conn.execute(self._sa["select"](self.messages).where(self.messages.c.id == message_id)).first()
        if not row:
            return None
        data = row._mapping
        if data["owner_id"] == owner_id:
            return row
        if access_token and secrets.compare_digest(str(data["access_token_hash"]), _token_hash(access_token)):
            return row
        return None

    def list_for_owner(self, owner_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        q = self._sa["select"](*self._message_projection()).where(self.messages.c.owner_id == owner_id).order_by(self.messages.c.updated_at.desc()).limit(max(1, min(int(limit), 200)))
        with self.engine.begin() as conn:
            rows = conn.execute(q).all()
        return [self._message_dict(row) for row in rows]

    def get_for_user(self, message_id: str, owner_id: str, access_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        row = self._authorised_row(message_id, owner_id, access_token)
        if not row:
            return None
        with self.engine.begin() as conn:
            replies = conn.execute(self._sa["select"](self.replies).where(self.replies.c.message_id == message_id).order_by(self.replies.c.created_at.asc())).all()
        item = self._message_dict(row)
        item["replies"] = [self._reply_dict(reply) for reply in replies]
        return item

    def mark_user_read(self, message_id: str, owner_id: str, access_token: Optional[str] = None) -> bool:
        if not self._authorised_row(message_id, owner_id, access_token):
            return False
        with self.engine.begin() as conn:
            result = conn.execute(self._sa["update"](self.messages).where(self.messages.c.id == message_id).values(user_read_at=_now()))
        return bool(result.rowcount)

    def list_admin(self, *, status: Optional[str] = None, category: Optional[str] = None, search: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        q = self._sa["select"](*self._message_projection())
        if status in VALID_STATUSES:
            q = q.where(self.messages.c.status == status)
        if category in VALID_CATEGORIES:
            q = q.where(self.messages.c.category == category)
        if search:
            term = f"%{search.strip().lower()[:120]}%"
            func, or_ = self._sa["func"], self._sa["or_"]
            q = q.where(or_(func.lower(self.messages.c.subject).like(term), func.lower(func.coalesce(self.messages.c.contact_email, "")).like(term)))
        q = q.order_by(self._sa["case"]((self.messages.c.admin_read_at.is_(None), 0), else_=1), self.messages.c.updated_at.desc()).limit(max(1, min(int(limit), 500))).offset(max(0, int(offset)))
        with self.engine.begin() as conn:
            rows = conn.execute(q).all()
        return [self._message_dict(row, include_private=True) for row in rows]

    def get_for_admin(self, message_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(self._sa["select"](self.messages).where(self.messages.c.id == message_id)).first()
            if not row:
                return None
            replies = conn.execute(self._sa["select"](self.replies).where(self.replies.c.message_id == message_id).order_by(self.replies.c.created_at.asc())).all()
        item = self._message_dict(row, include_private=True)
        item["replies"] = [self._reply_dict(reply, include_private=True) for reply in replies]
        return item

    def mark_admin_read(self, message_id: str) -> bool:
        func = self._sa["func"]
        with self.engine.begin() as conn:
            result = conn.execute(self._sa["update"](self.messages).where(self.messages.c.id == message_id).values(admin_read_at=func.coalesce(self.messages.c.admin_read_at, _now())))
        return bool(result.rowcount)

    def add_reply(self, *, message_id: str, reply: str, admin_email: str, email_requested: bool) -> Optional[Dict[str, Any]]:
        now = _now()
        reply_id = f"reply_{uuid.uuid4().hex}"
        with self.engine.begin() as conn:
            exists = conn.execute(self._sa["select"](self.messages.c.id).where(self.messages.c.id == message_id)).first()
            if not exists:
                return None
            conn.execute(self._sa["insert"](self.replies).values(id=reply_id, message_id=message_id, reply=reply, admin_email=admin_email, email_requested=bool(email_requested), email_status="pending", email_error=None, created_at=now))
            conn.execute(self._sa["update"](self.messages).where(self.messages.c.id == message_id).values(status="replied", updated_at=now, user_read_at=None, admin_read_at=self._sa["func"].coalesce(self.messages.c.admin_read_at, now)))
        return self.get_reply(reply_id, include_private=True)

    def get_reply(self, reply_id: str, *, include_private: bool = False) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(self._sa["select"](self.replies).where(self.replies.c.id == reply_id)).first()
        return self._reply_dict(row, include_private=include_private) if row else None

    def update_reply_delivery(self, reply_id: str, status: str, error: Optional[str]) -> None:
        with self.engine.begin() as conn:
            conn.execute(self._sa["update"](self.replies).where(self.replies.c.id == reply_id).values(email_status=status[:40], email_error=error[:300] if error else None))

    def update_status(self, message_id: str, status: str) -> bool:
        if status not in VALID_STATUSES:
            return False
        with self.engine.begin() as conn:
            result = conn.execute(self._sa["update"](self.messages).where(self.messages.c.id == message_id).values(status=status, updated_at=_now()))
        return bool(result.rowcount)

    def summary(self) -> Dict[str, int]:
        select, func = self._sa["select"], self._sa["func"]
        with self.engine.begin() as conn:
            rows = conn.execute(select(self.messages.c.status, func.count().label("total")).group_by(self.messages.c.status)).all()
            unread = conn.execute(select(func.count()).where(self.messages.c.admin_read_at.is_(None))).scalar_one()
            total = conn.execute(select(func.count()).select_from(self.messages)).scalar_one()
        result = {status: 0 for status in VALID_STATUSES}
        result.update({str(row.status): int(row.total) for row in rows})
        result["unread"] = int(unread)
        result["total"] = int(total)
        return result

    def purge_expired(self) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(self._sa["delete"](self.messages).where(self.messages.c.expires_at < _now()))
        return int(result.rowcount or 0)

    def delete_for_owners(self, owner_ids: Iterable[str]) -> int:
        clean = [str(value) for value in owner_ids if value]
        if not clean:
            return 0
        with self.engine.begin() as conn:
            result = conn.execute(self._sa["delete"](self.messages).where(self.messages.c.owner_id.in_(clean)))
        return int(result.rowcount or 0)


class MessageStore:
    """Select PostgreSQL/shared SQL in production and SQLite when explicitly requested."""
    def __init__(self, project_root: str, db_path: Optional[str] = None) -> None:
        database_url = os.getenv("MESSAGE_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not db_path and database_url and not database_url.strip().lower().startswith("sqlite"):
            self._impl = _SQLMessageStore(database_url)
        else:
            self._impl = _SQLiteMessageStore(project_root, db_path=db_path)

    def __getattr__(self, name: str):
        return getattr(self._impl, name)
