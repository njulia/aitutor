"""Account, student and subscription persistence.

Billing belongs to an account. Learning records continue to use student_id.
Existing users are migrated lazily: the first authenticated request creates an
account and one default student.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional

DB_PATH = os.getenv(
    "ACCOUNT_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "accounts.db"),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_account_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                name TEXT NOT NULL,
                year_group INTEGER NOT NULL,
                age INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_students_account ON students(account_id);
            CREATE TABLE IF NOT EXISTS account_subscriptions (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                expires_at TEXT,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_subscriptions_account ON account_subscriptions(account_id);
            """
        )


def ensure_account(email: str, display_name: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
    email = email.strip().lower()
    init_account_db()
    with _db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
        if row:
            return dict(row)
        now = _now()
        account_id = f"acct_{uuid.uuid4().hex}"
        conn.execute(
            "INSERT INTO accounts(id,email,display_name,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (account_id, email, display_name or email.split("@")[0], role, now, now),
        )
        return dict(conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone())


def get_account_by_email(email: str) -> Optional[Dict[str, Any]]:
    init_account_db()
    with _db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE email=?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None


def ensure_default_student(account_id: str, name: str = "Student", year_group: int = 3, age: int = 7) -> Dict[str, Any]:
    students = list_students(account_id, active_only=True)
    if students:
        return students[0]
    return create_student(account_id, name, year_group, age)


def create_student(account_id: str, name: str, year_group: int, age: int) -> Dict[str, Any]:
    init_account_db()
    now = _now()
    student_id = f"stu_{uuid.uuid4().hex}"
    with _db() as conn:
        conn.execute(
            "INSERT INTO students(id,account_id,name,year_group,age,is_active,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)",
            (student_id, account_id, name.strip(), year_group, age, now, now),
        )
        return dict(conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone())


def list_students(account_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
    init_account_db()
    query = "SELECT * FROM students WHERE account_id=?"
    params: List[Any] = [account_id]
    if active_only:
        query += " AND is_active=1"
    query += " ORDER BY created_at"
    with _db() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_student(student_id: str) -> Optional[Dict[str, Any]]:
    init_account_db()
    with _db() as conn:
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        return dict(row) if row else None


def student_belongs_to_account(student_id: str, account_id: str) -> bool:
    init_account_db()
    with _db() as conn:
        row = conn.execute("SELECT 1 FROM students WHERE id=? AND account_id=? AND is_active=1", (student_id, account_id)).fetchone()
        return bool(row)


def update_student(student_id: str, account_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
    allowed = {"name", "year_group", "age", "is_active"}
    values = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not values:
        return get_student(student_id)
    values["updated_at"] = _now()
    assignments = ", ".join(f"{k}=?" for k in values)
    with _db() as conn:
        conn.execute(
            f"UPDATE students SET {assignments} WHERE id=? AND account_id=?",
            (*values.values(), student_id, account_id),
        )
        row = conn.execute("SELECT * FROM students WHERE id=? AND account_id=?", (student_id, account_id)).fetchone()
        return dict(row) if row else None


def create_subscription(
    account_id: str,
    plan: str,
    status: str,
    duration_days: int,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
) -> Dict[str, Any]:
    init_account_db()
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    sub_id = f"sub_{uuid.uuid4().hex}"
    expires = (now_dt + timedelta(days=duration_days)).isoformat()
    with _db() as conn:
        conn.execute(
            """INSERT INTO account_subscriptions
            (id,account_id,plan,status,starts_at,expires_at,stripe_customer_id,stripe_subscription_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (sub_id, account_id, plan, status, now, expires, stripe_customer_id, stripe_subscription_id, now, now),
        )
        return dict(conn.execute("SELECT * FROM account_subscriptions WHERE id=?", (sub_id,)).fetchone())


def get_active_subscription(account_id: str) -> Optional[Dict[str, Any]]:
    init_account_db()
    now = _now()
    with _db() as conn:
        row = conn.execute(
            """SELECT * FROM account_subscriptions
               WHERE account_id=? AND status='active' AND (expires_at IS NULL OR expires_at>?)
               ORDER BY created_at DESC LIMIT 1""",
            (account_id, now),
        ).fetchone()
        return dict(row) if row else None


def account_has_active_subscription(email: str) -> bool:
    account = get_account_by_email(email)
    return bool(account and get_active_subscription(account["id"]))


def get_account_overview(email: str) -> Dict[str, Any]:
    account = ensure_account(email)
    student = ensure_default_student(account["id"])
    return {
        "account": account,
        "students": list_students(account["id"]),
        "default_student_id": student["id"],
        "subscription": get_active_subscription(account["id"]),
    }
