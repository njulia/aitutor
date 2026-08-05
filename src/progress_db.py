#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PostgreSQL-ready progress and authentication persistence.

Production: set ``DATABASE_URL=postgresql+psycopg://...``.
Local development and tests fall back to SQLite. Raw learner questions,
answers and AI feedback are not stored unless ``STORE_RAW_LEARNER_CONTENT`` is
explicitly enabled by the operator.
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus
import binascii
import hashlib
import hmac
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError

from src.webapp.db import get_engine, normalise_database_url

_DEFAULT = Path(__file__).resolve().parents[1] / "data" / "aitutor.db"
_URL = normalise_database_url(os.getenv("PROGRESS_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite+pysqlite:///{_DEFAULT}")
_engine = get_engine(_URL)
metadata = MetaData()

progress_students = Table(
    "progress_students", metadata,
    Column("student_id", String(80), primary_key=True),
    Column("name", String(80), nullable=False, default="Learner"),
    Column("year_group", Integer, nullable=False, default=3),
    Column("age", Integer, nullable=False, default=7),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
)
homework_sessions = Table(
    "homework_sessions", metadata,
    Column("id", String(80), primary_key=True),
    Column("student_id", String(80), nullable=False, index=True),
    Column("subject", String(80), nullable=False, index=True),
    Column("year_group", Integer, nullable=False, default=3),
    Column("homework_content", Text, nullable=True),
    Column("student_answers", Text, nullable=True),
    Column("score", Float, nullable=True),
    Column("max_score", Float, nullable=True),
    Column("review_text", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
)
topic_progress = Table(
    "topic_progress", metadata,
    Column("id", String(80), primary_key=True),
    Column("student_id", String(80), nullable=False, index=True),
    Column("subject", String(80), nullable=False),
    Column("topic", String(80), nullable=False),
    Column("questions_attempted", Integer, nullable=False, default=0),
    Column("questions_correct", Integer, nullable=False, default=0),
    Column("accuracy", Float, nullable=False, default=0.0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("student_id", "subject", "topic", name="uq_progress_topic"),
)
practice_sessions = Table(
    "practice_sessions", metadata,
    Column("id", String(80), primary_key=True),
    Column("student_id", String(80), nullable=False, index=True),
    Column("subject", String(80), nullable=False),
    Column("topic", String(80), nullable=False),
    Column("questions_count", Integer, nullable=False, default=0),
    Column("correct_count", Integer, nullable=False, default=0),
    Column("duration_seconds", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
legacy_subscriptions = Table(
    "legacy_local_subscriptions", metadata,
    Column("id", String(80), primary_key=True),
    Column("customer_email", String(254), nullable=False, index=True),
    Column("customer_name", String(80), nullable=False),
    Column("status", String(30), nullable=False),
    Column("product_name", String(80), nullable=False),
    Column("duration_days", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("is_dev", Boolean, nullable=False, default=True),
)
auth_users = Table(
    "auth_users", metadata,
    Column("username", String(254), primary_key=True),
    Column("password_hash", String(128), nullable=False),
    Column("salt", String(64), nullable=False),
    Column("is_test", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
ai_requests = Table(
    "ai_requests", metadata,
    Column("id", String(80), primary_key=True),
    Column("request_id", String(100), nullable=False, index=True),
    Column("timestamp", DateTime(timezone=True), nullable=False, index=True),
    Column("provider", String(80), nullable=False),
    Column("model", String(120), nullable=False),
    Column("operation", String(80), nullable=True),
    Column("prompt_tokens", Integer, nullable=True),
    Column("completion_tokens", Integer, nullable=True),
    Column("total_tokens", Integer, nullable=True),
    Column("latency_ms", Float, nullable=True),
    Column("status", String(30), nullable=False),
    Column("error_message", Text, nullable=True),
    Column("prompt_text", Text, nullable=True),
    Column("response_text", Text, nullable=True),
    Column("rag_context", Text, nullable=True),
    Column("student_id", String(80), nullable=True, index=True),
    Column("subject", String(80), nullable=True),
    Column("homework_doc_id", String(100), nullable=True),
    Column("langfuse_trace_id", String(100), nullable=True),
    Column("metadata_json", Text, nullable=True),
)
metadata.create_all(_engine)


def _now() -> datetime:
    return datetime.now(UTC)


def _dict(row: Any) -> Dict[str, Any]:
    data = dict(row._mapping)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, bool):
            data[key] = int(value)
    return data


def init_db() -> None:
    metadata.create_all(_engine)


def _raw_storage_enabled() -> bool:
    return os.getenv("STORE_RAW_LEARNER_CONTENT", "false").lower() in {"1", "true", "yes", "on"}


def _upsert_topic_progress(conn, student_id: str, subject: str, score: float, max_score: float, now: datetime) -> None:
    """向 topic_progress 表插入或更新某个科目的累计答题数据。"""
    clean_subject = subject[:80]
    # 用法科目本身作为 topic（因为没有更细粒度的 topic 信息）
    topic = clean_subject
    attempted = int(max_score or 0)
    correct = int(score or 0)
    if attempted <= 0:
        return
    existing = conn.execute(
        select(topic_progress.c.questions_attempted, topic_progress.c.questions_correct)
        .where(
            and_(
                topic_progress.c.student_id == student_id,
                topic_progress.c.subject == clean_subject,
                topic_progress.c.topic == topic,
            )
        )
    ).first()
    if existing:
        new_attempted = int(existing._mapping["questions_attempted"] or 0) + attempted
        new_correct = int(existing._mapping["questions_correct"] or 0) + correct
        new_accuracy = round(new_correct / new_attempted * 100, 1) if new_attempted > 0 else 0.0
        conn.execute(
            update(topic_progress)
            .where(
                and_(
                    topic_progress.c.student_id == student_id,
                    topic_progress.c.subject == clean_subject,
                    topic_progress.c.topic == topic,
                )
            )
            .values(
                questions_attempted=new_attempted,
                questions_correct=new_correct,
                accuracy=new_accuracy,
                updated_at=now,
            )
        )
    else:
        new_accuracy = round(correct / attempted * 100, 1) if attempted > 0 else 0.0
        conn.execute(
            insert(topic_progress).values(
                id=f"tp_{uuid.uuid4().hex}",
                student_id=student_id,
                subject=clean_subject,
                topic=topic,
                questions_attempted=attempted,
                questions_correct=correct,
                accuracy=new_accuracy,
                updated_at=now,
            )
        )


def save_homework_session(
    student_id: str,
    subject: str,
    year_group: int,
    homework_content: str,
    student_answers: str,
    score: float = None,
    review_text: str = None,
    max_score: float = 10,
) -> str:
    now = _now()
    session_id = f"hw_{uuid.uuid4().hex}"
    store_raw = _raw_storage_enabled()
    with _engine.begin() as conn:
        if not conn.execute(select(progress_students.c.student_id).where(progress_students.c.student_id == student_id)).first():
            try:
                conn.execute(insert(progress_students).values(
                    student_id=student_id, name="Learner", year_group=int(year_group), age=max(5, min(12, int(year_group)+4)),
                    created_at=now, updated_at=now, is_active=True,
                ))
            except IntegrityError:
                pass
        conn.execute(insert(homework_sessions).values(
            id=session_id, student_id=student_id, subject=subject[:80], year_group=int(year_group),
            homework_content=homework_content if store_raw else None,
            student_answers=student_answers if store_raw else None,
            score=score, max_score=max_score,
            review_text=review_text if store_raw else None,
            created_at=now,
        ))
        # 同步更新 topic_progress 表，供进度页面的 "Topic Progress" 使用
        _upsert_topic_progress(conn, student_id, subject[:80], score, max_score, now)
    return session_id


def get_progress_summary(student_id: str) -> Dict[str, Any]:
    with _engine.begin() as conn:
        rows = conn.execute(
            select(
                homework_sessions.c.subject, homework_sessions.c.score,
                homework_sessions.c.max_score, homework_sessions.c.created_at,
            )
            .where(homework_sessions.c.student_id == student_id)
            .order_by(homework_sessions.c.created_at.desc())
        ).all()
    graded = []
    by_subject: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        data = row._mapping
        if data["score"] is None or not data["max_score"]:
            continue
        ratio = max(0.0, min(float(data["score"]) / float(data["max_score"]), 1.0))
        graded.append(ratio)
        by_subject[str(data["subject"])].append(ratio)
    overall_accuracy = round(sum(graded) / len(graded) * 100, 1) if graded else 0
    subjects = [
        {
            "subject": subject,
            "count": len(values),
            "avg_accuracy": round(sum(values) / len(values) * 100, 1),
        }
        for subject, values in sorted(by_subject.items())
    ]
    latest = rows[0]._mapping if rows else None
    return {
        "student_id": student_id,
        "total_sessions": len(rows),
        "graded_sessions": len(graded),
        "average_accuracy": overall_accuracy,
        # Kept for older clients; this is now an accuracy percentage.
        "average_score": overall_accuracy,
        "subjects": subjects,
        "latest_session": dict(latest) if latest else None,
    }


def get_score_history(student_id: str, subject: str = None, limit: int = 50) -> List[Dict]:
    q = select(homework_sessions.c.subject, homework_sessions.c.score, homework_sessions.c.max_score, homework_sessions.c.created_at).where(and_(homework_sessions.c.student_id == student_id, homework_sessions.c.score.is_not(None)))
    if subject:
        q = q.where(homework_sessions.c.subject == subject)
    with _engine.begin() as conn:
        rows = conn.execute(q.order_by(homework_sessions.c.created_at.desc()).limit(max(1, min(limit, 500)))).all()
    return [_dict(r) for r in rows]


def get_topic_progress(student_id: str, subject: str = None) -> List[Dict]:
    q = select(topic_progress.c.subject, topic_progress.c.topic, topic_progress.c.questions_attempted, topic_progress.c.questions_correct, topic_progress.c.accuracy, topic_progress.c.updated_at).where(topic_progress.c.student_id == student_id)
    if subject:
        q = q.where(topic_progress.c.subject == subject)
    with _engine.begin() as conn:
        rows = conn.execute(q.order_by(topic_progress.c.accuracy.asc())).all()
    return [_dict(r) for r in rows]


def get_daily_goal_stats(student_id: str, daily_goal: int = 1) -> Dict[str, Any]:
    since = _now() - timedelta(days=30)
    with _engine.begin() as conn:
        timestamps = conn.execute(select(homework_sessions.c.created_at).where(and_(homework_sessions.c.student_id == student_id, homework_sessions.c.created_at >= since))).scalars().all()
    counts: Dict[date, int] = defaultdict(int)
    for stamp in timestamps:
        counts[stamp.date()] += 1
    active_days = len(counts)
    completed_days = sum(1 for value in counts.values() if value >= daily_goal)
    return {
        "daily_goal": daily_goal,
        "active_days": active_days,
        "days_goal_met": completed_days,
        "daily_goal_rate": round((completed_days / active_days * 100), 1) if active_days else 0,
        "daily_counts": [{"date": day.isoformat(), "count": counts[day]} for day in sorted(counts)],
    }


def get_streak_info(student_id: str) -> Dict[str, Any]:
    with _engine.begin() as conn:
        stamps = conn.execute(select(homework_sessions.c.created_at).where(homework_sessions.c.student_id == student_id)).scalars().all()
    days = sorted({stamp.date() for stamp in stamps})
    if not days:
        return {"current_streak": 0, "longest_streak": 0, "last_active_date": None}
    longest = current = 1
    for previous, current_day in zip(days, days[1:]):
        if (current_day - previous).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    today = _now().date()
    if (today - days[-1]).days > 1:
        current = 0
    else:
        current = 1
        cursor = days[-1]
        for prior in reversed(days[:-1]):
            if (cursor - prior).days == 1:
                current += 1
                cursor = prior
            else:
                break
    return {"current_streak": current, "longest_streak": longest, "last_active_date": days[-1].isoformat()}


def get_accuracy_rate(student_id: str) -> Dict[str, Any]:
    with _engine.begin() as conn:
        rows = conn.execute(select(homework_sessions.c.score, homework_sessions.c.max_score).where(and_(homework_sessions.c.student_id == student_id, homework_sessions.c.score.is_not(None)))).all()
    ratios = [float(r._mapping["score"]) / float(r._mapping["max_score"] or 10) for r in rows if float(r._mapping["max_score"] or 10) > 0]
    rate = round(sum(ratios) / len(ratios) * 100, 1) if ratios else 0
    return {"accuracy_rate": rate, "graded_sessions": len(ratios)}


def generate_progress_feedback(total_sessions: int, avg_accuracy: float, current_streak: int, daily_goal_rate: float) -> str:
    if total_sessions == 0:
        return "Ready to begin! Try one short activity and celebrate the effort."
    if avg_accuracy >= 85:
        return "Excellent work! Keep practising and try a slightly harder challenge next."
    if avg_accuracy >= 65:
        return "Good progress. Review one tricky topic and take it step by step."
    return "Every try helps your brain grow. Practise one small step at a time and ask for a hint when needed."


def list_all_students(limit: int = 100, offset: int = 0) -> List[Dict]:
    with _engine.begin() as conn:
        rows = conn.execute(select(progress_students).order_by(progress_students.c.created_at.desc()).limit(max(1,min(limit,10000))).offset(max(0,offset))).all()
    return [_dict(r) for r in rows]


def get_student_detail(student_id: str) -> Optional[Dict]:
    with _engine.begin() as conn:
        row = conn.execute(select(progress_students).where(progress_students.c.student_id == student_id)).first()
        if not row:
            return None
        sessions = conn.execute(select(homework_sessions.c.id, homework_sessions.c.subject, homework_sessions.c.score, homework_sessions.c.created_at).where(homework_sessions.c.student_id == student_id).order_by(homework_sessions.c.created_at.desc()).limit(20)).all()
    data = _dict(row)
    data["sessions"] = [_dict(r) for r in sessions]
    data["topics"] = get_topic_progress(student_id)
    return data


def update_student(student_id: str, **kwargs) -> bool:
    allowed = {"name", "year_group", "age", "is_active"}
    values = {key: value for key, value in kwargs.items() if key in allowed}
    if not values:
        return False
    values["updated_at"] = _now()
    with _engine.begin() as conn:
        result = conn.execute(update(progress_students).where(progress_students.c.student_id == student_id).values(**values))
    return bool(result.rowcount)


def delete_student(student_id: str) -> bool:
    with _engine.begin() as conn:
        conn.execute(delete(topic_progress).where(topic_progress.c.student_id == student_id))
        conn.execute(delete(practice_sessions).where(practice_sessions.c.student_id == student_id))
        conn.execute(delete(homework_sessions).where(homework_sessions.c.student_id == student_id))
        result = conn.execute(delete(progress_students).where(progress_students.c.student_id == student_id))
    return bool(result.rowcount)


def create_student(name: str, year_group: int = 3, age: int = 8) -> Dict[str, Any]:
    student_id = f"legacy_{uuid.uuid4().hex[:12]}"
    now = _now()
    with _engine.begin() as conn:
        conn.execute(insert(progress_students).values(student_id=student_id, name=" ".join(name.split())[:80], year_group=year_group, age=age, created_at=now, updated_at=now, is_active=True))
    return {"student_id": student_id, "name": name, "year_group": year_group, "age": age, "is_active": 1, "created_at": now.isoformat()}


def get_students_subject_breakdown(student_ids: List[str], since: datetime = None) -> Dict[str, List[Dict[str, Any]]]:
    """根据学生ID列表，查询 homework_sessions 中各科目的答题情况。

    返回: {student_id: [{subject, attempted, correct, accuracy}, ...]}
    """
    if not student_ids:
        return {}
    cutoff = since or (_now() - timedelta(hours=24))
    with _engine.begin() as conn:
        rows = conn.execute(
            select(
                homework_sessions.c.student_id,
                homework_sessions.c.subject,
                func.count().label("total_attempted"),
                func.sum(homework_sessions.c.score).label("total_correct"),
                func.max(homework_sessions.c.max_score).label("max_score_val"),
            )
            .where(
                and_(
                    homework_sessions.c.student_id.in_(student_ids),
                    homework_sessions.c.created_at >= cutoff,
                    homework_sessions.c.score.is_not(None),
                )
            )
            .group_by(homework_sessions.c.student_id, homework_sessions.c.subject)
        ).all()

    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        sid = row._mapping["student_id"]
        attempted = int(row._mapping["total_attempted"] or 0)
        correct = int(row._mapping["total_correct"] or 0)
        max_score = int(row._mapping["max_score_val"] or 10)
        if sid not in result:
            result[sid] = []
        result[sid].append({
            "subject": row._mapping["subject"],
            "attempted": attempted,
            "correct": correct,
            "accuracy": round(correct / (attempted * max_score) * 100) if attempted > 0 else 0,
        })
    return result


def get_all_sessions_summary() -> Dict[str, Any]:
    with _engine.begin() as conn:
        total = conn.execute(select(func.count()).select_from(homework_sessions)).scalar_one()
        avg = conn.execute(select(func.avg(homework_sessions.c.score)).where(homework_sessions.c.score.is_not(None))).scalar()
        subjects = conn.execute(select(homework_sessions.c.subject, func.count().label("count"), func.avg(homework_sessions.c.score).label("avg_score")).where(homework_sessions.c.score.is_not(None)).group_by(homework_sessions.c.subject)).all()
    return {"total_sessions": int(total or 0), "average_score": round(float(avg),1) if avg is not None else None, "by_subject": [{"subject":r._mapping["subject"],"count":int(r._mapping["count"]),"avg_score":round(float(r._mapping["avg_score"]),1)} for r in subjects], "daily_activity": []}


def _hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return binascii.hexlify(hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)).decode()


def create_user(username: str, password: str) -> Dict[str, Any]:
    email = username.strip().lower()
    salt = os.urandom(16).hex()
    now = _now()
    try:
        with _engine.begin() as conn:
            conn.execute(insert(auth_users).values(username=email, password_hash=_hash_password(password,salt), salt=salt, is_test=False, created_at=now))
    except IntegrityError as exc:
        raise ValueError("User already exists") from exc
    return {"username": email, "created_at": now.isoformat()}


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with _engine.begin() as conn:
        row = conn.execute(select(auth_users).where(auth_users.c.username == username.strip().lower())).first()
    return _dict(row) if row else None


def verify_user_credentials(username: str, password: str) -> bool:
    user = get_user_by_username(username)
    return bool(user and hmac.compare_digest(_hash_password(password, user["salt"]), user["password_hash"]))


def set_user_password(username: str, new_password: str) -> bool:
    """Update a password using the same PBKDF2 scheme on SQLite or PostgreSQL."""
    if not 10 <= len(str(new_password or "")) <= 128 or str(new_password).isspace():
        raise ValueError("Use a password with at least 10 characters")
    salt = os.urandom(16).hex()
    with _engine.begin() as conn:
        result = conn.execute(
            update(auth_users)
            .where(auth_users.c.username == username.strip().lower())
            .values(password_hash=_hash_password(new_password, salt), salt=salt)
        )
    return bool(result.rowcount)


def ensure_user_columns():
    return None


def set_user_test_flag(username: str, is_test: bool) -> bool:
    with _engine.begin() as conn:
        result = conn.execute(update(auth_users).where(auth_users.c.username == username.strip().lower()).values(is_test=bool(is_test)))
    return bool(result.rowcount)


def is_user_test(username: str) -> bool:
    user = get_user_by_username(username)
    return bool(user and user.get("is_test"))


def create_local_subscription(customer_email: str, customer_name: str, product_name: str, duration_days: int) -> Dict[str, Any]:
    now = _now()
    expires = now + timedelta(days=duration_days)
    sub_id = f"dev_{uuid.uuid4().hex[:12]}"
    with _engine.begin() as conn:
        conn.execute(insert(legacy_subscriptions).values(id=sub_id, customer_email=customer_email.strip().lower(), customer_name=customer_name[:80], status="active", product_name=product_name[:80], duration_days=duration_days, created_at=now, expires_at=expires, is_dev=True))
    return {"subscription_id":sub_id,"customer_email":customer_email,"customer_name":customer_name,"status":"active","product_name":product_name,"duration_days":duration_days,"created_at":now.isoformat(),"expires_at":expires.isoformat(),"is_dev":True}


def list_local_subscriptions(limit: int = 100) -> List[Dict]:
    with _engine.begin() as conn:
        rows=conn.execute(select(legacy_subscriptions).order_by(legacy_subscriptions.c.created_at.desc()).limit(max(1,min(limit,1000)))).all()
    return [_dict(r) for r in rows]


def get_local_subscriptions_by_email(customer_email: str) -> List[Dict]:
    with _engine.begin() as conn:
        rows=conn.execute(select(legacy_subscriptions).where(legacy_subscriptions.c.customer_email==customer_email.strip().lower()).order_by(legacy_subscriptions.c.created_at.desc())).all()
    return [_dict(r) for r in rows]


def get_local_subscription_stats() -> Dict[str, Any]:
    items = list_local_subscriptions()
    now = _now()
    active = []
    for item in items:
        if item.get("status") == "active" and item.get("expires_at") is not None:
            try:
                expires_at = datetime.fromisoformat(item["expires_at"])
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if expires_at > now:
                    active.append(item)
            except (ValueError, TypeError):
                continue
    return {
        "active_subscriptions": len(active),
        "estimated_revenue_gbp": 0,
        "subscriptions": items,
    }


def list_all_users(limit: int = 100, offset: int = 0):
    with _engine.begin() as conn:
        rows=conn.execute(select(auth_users.c.username,auth_users.c.created_at,auth_users.c.is_test).order_by(auth_users.c.created_at.desc()).limit(max(1,min(limit,1000))).offset(max(0,offset))).all()
    return [_dict(r) for r in rows]


init_db()


def delete_user_account(username: str) -> bool:
    """Erase the parent login and legacy billing records for this email."""
    clean = username.strip().lower()
    with _engine.begin() as conn:
        conn.execute(delete(legacy_subscriptions).where(legacy_subscriptions.c.customer_email == clean))
        result = conn.execute(delete(auth_users).where(auth_users.c.username == clean))
    return bool(result.rowcount)


def database_health_check() -> bool:
    """Return True when the relational store accepts a simple query."""
    try:
        with _engine.connect() as conn:
            conn.execute(select(func.count()).select_from(auth_users)).scalar_one()
        return True
    except Exception:
        return False


def purge_old_learning_records(retention_days: Optional[int] = None) -> int:
    """Delete expired learning-session rows according to the configured policy.

    Raw learner content is already off by default. This cleanup also limits the
    lifetime of scores and timestamps used for progress views.
    """
    if retention_days is None:
        try:
            retention_days = int(os.getenv("LEARNING_RECORD_RETENTION_DAYS", "365"))
        except ValueError:
            retention_days = 365
    retention_days = max(30, min(int(retention_days), 2555))
    cutoff = _now() - timedelta(days=retention_days)
    with _engine.begin() as conn:
        result = conn.execute(delete(homework_sessions).where(homework_sessions.c.created_at < cutoff))
        conn.execute(delete(practice_sessions).where(practice_sessions.c.created_at < cutoff))
    return int(result.rowcount or 0)


def get_database_url() -> str:
    db_user = os.environ["DB_USER"]
    db_password = quote_plus(os.environ["DB_PASSWORD"])
    db_name = os.environ["DB_NAME"]
    connection_name = os.environ["INSTANCE_CONNECTION_NAME"]

    return (
        f"postgresql+psycopg://{db_user}:{db_password}"
        f"@/{db_name}"
        f"?host=/cloudsql/{connection_name}"
    )
