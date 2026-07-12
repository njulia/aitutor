"""Parent/guardian support messages backed by the main relational database."""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, and_, create_engine, delete, insert, select, update

from .db import engine_options, normalise_database_url

_MESSAGE_ENGINE = None
_MESSAGE_TABLE = None


class MessageCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=2, max_length=4000)
    contact_email: Optional[str] = Field(default=None, max_length=254)


class MessageReply(BaseModel):
    reply: str = Field(min_length=2, max_length=4000)


class StatusChange(BaseModel):
    status: str


def create_message_router(resolve_identity, project_root: str):
    global _MESSAGE_ENGINE, _MESSAGE_TABLE
    url = normalise_database_url(os.getenv("MESSAGE_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite+pysqlite:///{Path(project_root) / 'data' / 'messages.db'}")
    kwargs: Dict[str, Any] = engine_options(url)
    engine = create_engine(url, **kwargs)
    metadata = MetaData()
    messages = Table(
        "support_messages", metadata,
        Column("id", String(80), primary_key=True),
        Column("access_token", String(100), nullable=False),
        Column("owner_id", String(100), nullable=False, index=True),
        Column("subject", String(120), nullable=False),
        Column("message", Text, nullable=False),
        Column("contact_email", String(254), nullable=True),
        Column("reply", Text, nullable=True),
        Column("status", String(30), nullable=False, index=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    _MESSAGE_ENGINE = engine
    _MESSAGE_TABLE = messages
    router = APIRouter()

    def serialise(row: Any, *, admin: bool = False) -> Dict[str, Any]:
        data = dict(row._mapping)
        data.pop("access_token", None)
        if not admin:
            data.pop("contact_email", None)
        for key in ("created_at", "updated_at"):
            if hasattr(data.get(key), "isoformat"):
                data[key] = data[key].isoformat()
        return data

    @router.post("/api/messages")
    async def create_message(body: MessageCreate, request: Request):
        owner_id, username, new_anon = resolve_identity(request)
        now = datetime.now(UTC)
        message_id = f"msg_{uuid.uuid4().hex}"
        token = secrets.token_urlsafe(24)
        with engine.begin() as conn:
            conn.execute(insert(messages).values(
                id=message_id, access_token=token, owner_id=owner_id,
                subject=body.subject.strip(), message=body.message.strip(),
                contact_email=username or body.contact_email,
                reply=None, status="open", created_at=now, updated_at=now,
            ))
        response = {"success": True, "message_id": message_id, "access_token": token}
        if new_anon:
            response["anonymous_session_created"] = True
        return response

    @router.get("/api/messages/{message_id}")
    async def read_message(message_id: str, request: Request, access_token: Optional[str] = None):
        owner_id, _username, _ = resolve_identity(request)
        with engine.begin() as conn:
            row = conn.execute(select(messages).where(messages.c.id == message_id)).first()
        if not row or (row._mapping["owner_id"] != owner_id and row._mapping["access_token"] != access_token):
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "message": serialise(row)}

    @router.get("/api/admin/messages")
    async def admin_messages(limit: int = 100):
        with engine.begin() as conn:
            rows = conn.execute(select(
                messages.c.id, messages.c.subject, messages.c.status,
                messages.c.created_at, messages.c.updated_at,
            ).order_by(messages.c.created_at.desc()).limit(max(1, min(limit, 500)))).all()
        return {"success": True, "messages": [serialise(row, admin=True) for row in rows]}

    @router.get("/api/admin/messages/{message_id}")
    async def admin_message(message_id: str):
        with engine.begin() as conn:
            row = conn.execute(select(messages).where(messages.c.id == message_id)).first()
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "message": serialise(row, admin=True)}

    @router.post("/api/admin/messages/{message_id}/reply")
    async def admin_reply(message_id: str, body: MessageReply):
        with engine.begin() as conn:
            result = conn.execute(update(messages).where(messages.c.id == message_id).values(
                reply=body.reply.strip(), status="replied", updated_at=datetime.now(UTC)
            ))
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True}

    @router.patch("/api/admin/messages/{message_id}/status")
    async def admin_status(message_id: str, body: StatusChange):
        if body.status not in {"open", "pending", "replied", "closed"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        with engine.begin() as conn:
            result = conn.execute(update(messages).where(messages.c.id == message_id).values(
                status=body.status, updated_at=datetime.now(UTC)
            ))
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True}

    return router


def delete_messages_for_owners(owner_ids) -> int:
    """Erase support records belonging to pseudonymous learner/session owners."""
    if _MESSAGE_ENGINE is None or _MESSAGE_TABLE is None:
        return 0
    clean_ids = [str(value) for value in owner_ids if value]
    if not clean_ids:
        return 0
    with _MESSAGE_ENGINE.begin() as conn:
        result = conn.execute(delete(_MESSAGE_TABLE).where(_MESSAGE_TABLE.c.owner_id.in_(clean_ids)))
    return int(result.rowcount or 0)
