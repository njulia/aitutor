"""孩子登录会话存储。

孩子使用家庭码 + 孩子码登录，获得一个短期 token 用于访问 /app。
会话不存储任何个人数据，仅保存学生 ID 和过期时间。
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, DateTime, MetaData, String, Table, delete, select, insert,
)

from src.webapp.account_store import _engine


_metadata = MetaData()

kid_sessions = Table(
    "kid_sessions",
    _metadata,
    Column("token", String(64), primary_key=True),
    Column("student_id", String(80), nullable=False, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def init_kid_session_db() -> None:
    _engine()
    _metadata.create_all(_engine())


def create_kid_session(student_id: str, ttl_seconds: int = 3600) -> Dict[str, Any]:
    """为孩子创建一个登录会话，返回 token 和过期时间。"""
    token = secrets.token_urlsafe(32)
    now = _now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    with _engine().begin() as conn:
        conn.execute(
            insert(kid_sessions).values(
                token=token, student_id=student_id,
                expires_at=expires_at, created_at=now,
            )
        )
    return {"token": token, "expires_at": expires_at.isoformat()}


def resolve_kid_session(token: str) -> Optional[Dict[str, Any]]:
    """根据 token 解析孩子会话，返回学生 ID 或 None。"""
    if not token:
        return None
    with _engine().begin() as conn:
        row = conn.execute(
            select(kid_sessions).where(kid_sessions.c.token == token)
        ).first()
    if not row:
        return None
    data = {
        "student_id": row.student_id,
        "expires_at": row.expires_at,
    }
    if data["expires_at"].tzinfo is None:
        data["expires_at"] = data["expires_at"].replace(tzinfo=timezone.utc)
    if data["expires_at"] < _now():
        revoke_kid_session(token)
        return None
    return data


def revoke_kid_session(token: str) -> None:
    """撤销单个会话。"""
    with _engine().begin() as conn:
        conn.execute(delete(kid_sessions).where(kid_sessions.c.token == token))


def revoke_all_kid_sessions_for_student(student_id: str) -> int:
    """撤销某孩子的所有会话，用于家长登出或账号删除。"""
    with _engine().begin() as conn:
        result = conn.execute(
            delete(kid_sessions).where(kid_sessions.c.student_id == student_id)
        )
    return result.rowcount


def revoke_all_kid_sessions_for_account(account_id: str) -> int:
    """撤销某家庭所有孩子的会话，用于家长登出或账号删除。"""
    from src.webapp.account_store import students
    with _engine().begin() as conn:
        student_ids = [
            r.id for r in conn.execute(
                select(students.c.id).where(students.c.account_id == account_id)
            ).fetchall()
        ]
        if not student_ids:
            return 0
        result = conn.execute(
            delete(kid_sessions).where(kid_sessions.c.student_id.in_(student_ids))
        )
    return result.rowcount
