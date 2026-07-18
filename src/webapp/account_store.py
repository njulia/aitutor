"""PostgreSQL-ready account, learner and subscription persistence.

Production uses ``DATABASE_URL=postgresql+psycopg://...``. SQLite is retained
only as a zero-setup local/test fallback. Billing belongs to the parent account;
learner profiles are never sent to Stripe.
"""
from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    create_engine,
    func,
    delete,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .db import engine_options, normalise_database_url

DB_PATH = os.getenv(
    "ACCOUNT_DB_PATH",
    str(Path(__file__).resolve().parents[2] / "data" / "accounts.db"),
)
_INITIALISED_PATH: Optional[str] = None  # retained for backward-compatible tests
_INIT_LOCK = threading.Lock()
_ENGINE: Optional[Engine] = None
_ENGINE_URL: Optional[str] = None
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_metadata = MetaData()

accounts = Table(
    "accounts",
    _metadata,
    Column("id", String(80), primary_key=True),
    Column("email", String(254), nullable=False, unique=True, index=True),
    Column("display_name", String(80), nullable=True),
    Column("role", String(20), nullable=False, default="user"),
    Column("stripe_customer_id", String(100), nullable=True, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

students = Table(
    "students",
    _metadata,
    Column("id", String(80), primary_key=True),
    Column("account_id", String(80), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("name", String(80), nullable=False),  # nickname/display label only
    Column("year_group", Integer, nullable=False),
    Column("age", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("is_default", Boolean, nullable=False, default=False),
    # NULL for ordinary learners; account_id for the single default learner.
    Column("default_for_account", String(80), nullable=True, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

subscriptions = Table(
    "account_subscriptions",
    _metadata,
    Column("id", String(100), primary_key=True),
    Column("account_id", String(80), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("plan", String(80), nullable=False),
    Column("price_id", String(100), nullable=True),
    Column("status", String(30), nullable=False, index=True),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("current_period_end", DateTime(timezone=True), nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("cancel_at_period_end", Boolean, nullable=False, default=False),
    Column("stripe_customer_id", String(100), nullable=True, index=True),
    Column("stripe_subscription_id", String(100), nullable=True, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _database_url() -> str:
    configured = os.getenv("ACCOUNT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if configured:
        return normalise_database_url(configured)
    return f"sqlite+pysqlite:///{DB_PATH}"


def _engine() -> Engine:
    global _ENGINE, _ENGINE_URL, _INITIALISED_PATH
    url = _database_url()
    if _ENGINE is not None and _ENGINE_URL == url:
        return _ENGINE
    with _INIT_LOCK:
        if _ENGINE is not None and _ENGINE_URL == url:
            return _ENGINE
        kwargs: Dict[str, Any] = engine_options(url)
        if url.startswith("sqlite"):
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _ENGINE = create_engine(url, **kwargs)
        _ENGINE_URL = url
        _metadata.create_all(_ENGINE)
        _INITIALISED_PATH = DB_PATH
        return _ENGINE


def init_account_db() -> None:
    _engine()


def _normalise_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not _EMAIL_RE.fullmatch(value) or len(value) > 254:
        raise ValueError("A valid email address is required")
    return value


def _validate_student(name: str, year_group: int, age: int) -> tuple[str, int, int]:
    nickname = " ".join((name or "").split())
    if not nickname or len(nickname) > 40:
        raise ValueError("Learner nickname must be between 1 and 40 characters")
    if "@" in nickname or re.search(r"\b(?:school|road|street|avenue|postcode)\b", nickname, re.I):
        raise ValueError("Please use a nickname, not contact or school information")
    if not 1 <= int(year_group) <= 6:
        raise ValueError("Year group must be between 1 and 6")
    if not 5 <= int(age) <= 11:
        raise ValueError("Age must be between 5 and 11")
    return nickname, int(year_group), int(age)


def _dict(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    data = dict(row._mapping)
    # Keep old frontend contracts using 0/1 for booleans where needed.
    for key in ("is_active", "is_default", "cancel_at_period_end"):
        if key in data:
            data[key] = int(bool(data[key]))
    return data


def ensure_account(email: str, display_name: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
    clean_email = _normalise_email(email)
    clean_display = " ".join((display_name or clean_email.split("@", 1)[0]).split())[:80]
    safe_role = role if role in {"user", "admin"} else "user"
    engine = _engine()
    with engine.begin() as conn:
        row = conn.execute(select(accounts).where(accounts.c.email == clean_email)).first()
    if row is None:
        now = _now()
        try:
            with engine.begin() as conn:
                conn.execute(insert(accounts).values(
                    id=f"acct_{uuid.uuid4().hex}", email=clean_email,
                    display_name=clean_display, role=safe_role,
                    stripe_customer_id=None, created_at=now, updated_at=now,
                ))
        except IntegrityError:
            # Another worker created the same normalised account.
            pass
        with engine.begin() as conn:
            row = conn.execute(select(accounts).where(accounts.c.email == clean_email)).first()
    if row is None:
        raise RuntimeError("Unable to create or read account")
    return _dict(row) or {}


def get_account_by_email(email: str) -> Optional[Dict[str, Any]]:
    try:
        clean_email = _normalise_email(email)
    except ValueError:
        return None
    with _engine().begin() as conn:
        return _dict(conn.execute(select(accounts).where(accounts.c.email == clean_email)).first())


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    with _engine().begin() as conn:
        return _dict(conn.execute(select(accounts).where(accounts.c.id == account_id)).first())


def set_stripe_customer(account_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
    if not customer_id:
        raise ValueError("Stripe customer ID is required")
    with _engine().begin() as conn:
        conn.execute(
            update(accounts).where(accounts.c.id == account_id).values(
                stripe_customer_id=customer_id, updated_at=_now()
            )
        )
        return _dict(conn.execute(select(accounts).where(accounts.c.id == account_id)).first())


def ensure_default_student(account_id: str, name: str = "Learner", year_group: int = 3, age: int = 7) -> Dict[str, Any]:
    nickname, year_group, age = _validate_student(name, year_group, age)
    engine = _engine()
    with engine.begin() as conn:
        row = conn.execute(select(students).where(and_(
            students.c.account_id == account_id,
            students.c.default_for_account == account_id,
        ))).first()
        if row:
            return _dict(row) or {}
        account_exists = conn.execute(select(accounts.c.id).where(accounts.c.id == account_id)).first()
        existing = conn.execute(select(students).where(and_(
            students.c.account_id == account_id,
            students.c.is_active.is_(True),
        )).order_by(students.c.created_at).limit(1)).first()
    if not account_exists:
        raise ValueError("Account not found")
    now = _now()
    try:
        with engine.begin() as conn:
            if existing:
                conn.execute(update(students).where(students.c.id == existing._mapping["id"]).values(
                    is_default=True, default_for_account=account_id, updated_at=now
                ))
            else:
                conn.execute(insert(students).values(
                    id=f"stu_{uuid.uuid4().hex}", account_id=account_id, name=nickname,
                    year_group=year_group, age=age, is_active=True, is_default=True,
                    default_for_account=account_id, created_at=now, updated_at=now,
                ))
    except IntegrityError:
        # The unique default_for_account key makes this safe across workers.
        pass
    with engine.begin() as conn:
        row = conn.execute(select(students).where(and_(
            students.c.account_id == account_id,
            students.c.default_for_account == account_id,
        ))).first()
    if row is None:
        raise RuntimeError("Unable to create default learner")
    return _dict(row) or {}


def create_student(account_id: str, name: str, year_group: int, age: int) -> Dict[str, Any]:
    nickname, year_group, age = _validate_student(name, year_group, age)
    now = _now()
    learner_id = f"stu_{uuid.uuid4().hex}"
    with _engine().begin() as conn:
        if not conn.execute(select(accounts.c.id).where(accounts.c.id == account_id)).first():
            raise ValueError("Account not found")
        conn.execute(
            insert(students).values(
                id=learner_id, account_id=account_id, name=nickname,
                year_group=year_group, age=age, is_active=True, is_default=False,
                default_for_account=None, created_at=now, updated_at=now,
            )
        )
        row = conn.execute(select(students).where(students.c.id == learner_id)).first()
    return _dict(row) or {}


def list_students(account_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
    condition = students.c.account_id == account_id
    if active_only:
        condition = and_(condition, students.c.is_active.is_(True))
    with _engine().begin() as conn:
        rows = conn.execute(
            select(students).where(condition).order_by(students.c.is_default.desc(), students.c.created_at)
        ).all()
    return [_dict(row) or {} for row in rows]


def get_student(student_id: str) -> Optional[Dict[str, Any]]:
    with _engine().begin() as conn:
        return _dict(conn.execute(select(students).where(students.c.id == student_id)).first())


def student_belongs_to_account(student_id: str, account_id: str) -> bool:
    with _engine().begin() as conn:
        row = conn.execute(
            select(students.c.id).where(
                and_(students.c.id == student_id, students.c.account_id == account_id, students.c.is_active.is_(True))
            )
        ).first()
    return bool(row)


def update_student(student_id: str, account_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
    current = get_student(student_id)
    if not current or current["account_id"] != account_id:
        return None
    nickname, year_group, age = _validate_student(
        updates.get("name", current["name"]),
        updates.get("year_group", current["year_group"]),
        updates.get("age", current["age"]),
    )
    values = {
        "name": nickname, "year_group": year_group, "age": age,
        "is_active": bool(updates.get("is_active", current["is_active"])), "updated_at": _now(),
    }
    with _engine().begin() as conn:
        conn.execute(
            update(students).where(
                and_(students.c.id == student_id, students.c.account_id == account_id)
            ).values(**values)
        )
        row = conn.execute(select(students).where(students.c.id == student_id)).first()
    return _dict(row)


def delete_student(student_id: str, account_id: str) -> bool:
    with _engine().begin() as conn:
        result = conn.execute(
            delete(students).where(and_(students.c.id == student_id, students.c.account_id == account_id))
        )
    return bool(result.rowcount)


def create_subscription(
    account_id: str,
    plan: str,
    status: str,
    duration_days: int,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin/dev compatibility helper. Production access is webhook-driven."""
    now = _now()
    return upsert_stripe_subscription(
        account_id=account_id,
        plan=plan,
        status=status,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id or f"manual_{uuid.uuid4().hex}",
        price_id=None,
        current_period_end=now + timedelta(days=max(1, min(int(duration_days), 3660))),
        cancel_at_period_end=False,
    )


def upsert_stripe_subscription(
    *,
    account_id: str,
    plan: str,
    status: str,
    stripe_customer_id: Optional[str],
    stripe_subscription_id: str,
    price_id: Optional[str],
    current_period_end: Optional[datetime],
    cancel_at_period_end: bool,
) -> Dict[str, Any]:
    allowed = {"active", "trialing", "past_due", "unpaid", "canceled", "cancelled", "incomplete", "incomplete_expired", "paused", "expired"}
    clean_status = status.lower().strip()
    if clean_status not in allowed:
        clean_status = "incomplete"
    if clean_status == "canceled":
        clean_status = "cancelled"
    now = _now()
    with _engine().begin() as conn:
        row = conn.execute(
            select(subscriptions).where(subscriptions.c.stripe_subscription_id == stripe_subscription_id)
        ).first()
        values = dict(
            account_id=account_id, plan=(plan or "premium")[:80], price_id=price_id,
            status=clean_status, current_period_end=current_period_end,
            expires_at=current_period_end, cancel_at_period_end=bool(cancel_at_period_end),
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id, updated_at=now,
        )
        if row:
            conn.execute(update(subscriptions).where(subscriptions.c.id == row._mapping["id"]).values(**values))
            sub_id = row._mapping["id"]
        else:
            sub_id = f"subrec_{uuid.uuid4().hex}"
            conn.execute(insert(subscriptions).values(id=sub_id, starts_at=now, created_at=now, **values))
        if stripe_customer_id:
            conn.execute(update(accounts).where(accounts.c.id == account_id).values(
                stripe_customer_id=stripe_customer_id, updated_at=now
            ))
        result = conn.execute(select(subscriptions).where(subscriptions.c.id == sub_id)).first()
    return _dict(result) or {}


def get_subscription_by_stripe_id(stripe_subscription_id: str) -> Optional[Dict[str, Any]]:
    with _engine().begin() as conn:
        return _dict(conn.execute(
            select(subscriptions).where(subscriptions.c.stripe_subscription_id == stripe_subscription_id)
        ).first())


def get_active_subscription(account_id: str) -> Optional[Dict[str, Any]]:
    now = _now()
    with _engine().begin() as conn:
        row = conn.execute(
            select(subscriptions).where(
                and_(
                    subscriptions.c.account_id == account_id,
                    subscriptions.c.status.in_(["active", "trialing"]),
                    subscriptions.c.current_period_end > now,
                )
            ).order_by(subscriptions.c.created_at.desc()).limit(1)
        ).first()
    return _dict(row)


def account_has_active_subscription(email: str, required_plans: Optional[List[str]] = None) -> bool:
    account = get_account_by_email(email)
    if not account:
        return False
    sub = get_active_subscription(account["id"])
    if not sub:
        return False
    if required_plans:
        # family_monthly is a super-set that includes everything
        effective_required = set(required_plans)
        if sub.get("plan") == "family_monthly":
            return True
        return sub.get("plan") in effective_required
    return True


def get_account_overview(email: str) -> Dict[str, Any]:
    account = ensure_account(email)
    default = ensure_default_student(account["id"])
    return {
        "account": account,
        "students": list_students(account["id"]),
        "default_student_id": default["id"],
        "subscription": get_active_subscription(account["id"]),
    }


def get_account_by_stripe_customer_id(customer_id: str) -> Optional[Dict[str, Any]]:
    if not customer_id:
        return None
    with _engine().begin() as conn:
        return _dict(conn.execute(
            select(accounts).where(accounts.c.stripe_customer_id == customer_id)
        ).first())


def list_subscriptions(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List locally materialised Stripe entitlements for the admin dashboard."""
    with _engine().begin() as conn:
        rows = conn.execute(
            select(subscriptions)
            .order_by(subscriptions.c.created_at.desc())
            .limit(max(1, min(int(limit), 1000)))
            .offset(max(0, int(offset)))
        ).all()
    return [_dict(row) or {} for row in rows]


def get_subscription_stats() -> Dict[str, Any]:
    """Return entitlement counts from PostgreSQL, not a live Stripe list call."""
    now = _now()
    with _engine().begin() as conn:
        active = conn.execute(
            select(func.count()).select_from(subscriptions).where(
                and_(
                    subscriptions.c.status.in_(["active", "trialing"]),
                    subscriptions.c.current_period_end > now,
                )
            )
        ).scalar_one()
        total = conn.execute(select(func.count()).select_from(subscriptions)).scalar_one()
    return {
        "active_subscriptions": int(active or 0),
        "total_subscription_records": int(total or 0),
        "subscriptions": list_subscriptions(limit=100),
        "source": "local_webhook_materialisation",
    }


def delete_account(account_id: str) -> bool:
    """Delete the parent account and its learners/entitlements.

    Explicit child deletes also make the local SQLite development fallback
    behave like PostgreSQL's ON DELETE CASCADE.
    """
    with _engine().begin() as conn:
        conn.execute(delete(subscriptions).where(subscriptions.c.account_id == account_id))
        conn.execute(delete(students).where(students.c.account_id == account_id))
        result = conn.execute(delete(accounts).where(accounts.c.id == account_id))
    return bool(result.rowcount)
