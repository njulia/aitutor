"""Contact pages and support-message API routes."""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from src.webapp.email_service import send_support_reply
from .message_models import AdminReplyCreate, MessageCreate, StatusChange
from .message_store import MessageStore, VALID_CATEGORIES, VALID_STATUSES

_STORE: Optional[MessageStore] = None
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _clean_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    email = value.strip().lower()
    if len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Please enter a valid parent or guardian email address.")
    return email


def _safe_page(project_root: str, filename: str) -> FileResponse:
    path = Path(project_root) / "static" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(
        str(path),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def create_message_router(
    *,
    resolve_identity: Callable,
    require_admin: Callable,
    project_root: str,
) -> APIRouter:
    """Build the contact-message router.

    ``resolve_identity`` returns ``(student_or_anon_id, account_email,
    new_anon_cookie)``. Support messages are owned by the parent account when
    logged in, not by whichever child profile is selected.
    """
    global _STORE
    store = MessageStore(project_root)
    store.purge_expired()
    _STORE = store
    router = APIRouter()

    def user_identity(request: Request):
        identity_id, account_email, new_anon = resolve_identity(request)
        account_email = account_email.strip().lower() if account_email else None
        owner_id = f"account:{account_email}" if account_email else f"anonymous:{identity_id}"
        return owner_id, account_email, new_anon

    def token_from(request: Request) -> Optional[str]:
        token = (request.headers.get("X-Message-Access-Token") or "").strip()
        return token or None

    @router.get("/messages")
    async def messages_page():
        return _safe_page(project_root, "messages.html")

    @router.get("/contact-me", include_in_schema=False)
    async def legacy_contact_page():
        return RedirectResponse("/messages", status_code=308)

    @router.get("/admin/messages")
    async def admin_messages_page(request: Request):
        require_admin(request)
        return _safe_page(project_root, "admin-messages.html")

    @router.post("/api/messages")
    async def create_message(body: MessageCreate, request: Request):
        owner_id, account_email, new_anon = user_identity(request)
        contact_email = account_email or _clean_email(body.contact_email)
        if not contact_email:
            raise HTTPException(
                status_code=400,
                detail="A parent or guardian email is required so support can reply.",
            )
        category = body.category.strip().lower()
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail="Please choose a valid message category.")
        subject = body.subject.strip()
        message = body.message.strip()
        if len(subject) < 2 or len(message) < 2:
            raise HTTPException(status_code=400, detail="Please add a subject and a message.")

        admin_item, access_token = await asyncio.to_thread(
            store.create_message,
            owner_id=owner_id,
            contact_email=contact_email,
            category=category,
            subject=subject,
            message=message,
        )
        item = await asyncio.to_thread(
            store.get_for_user, admin_item["id"], owner_id, access_token
        )
        response = JSONResponse(
            {
                "success": True,
                "message": item,
                # Only returned once. The database stores a one-way hash.
                "access_token": access_token,
            },
            status_code=201,
        )
        if new_anon:
            response.set_cookie(
                "anon_session_id",
                new_anon,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="lax",
                secure=not os.getenv("DEV_MODE", "").lower() in {"1", "true", "yes"},
            )
        return response

    @router.get("/api/messages")
    async def list_messages(request: Request, limit: int = 100):
        owner_id, _account_email, _new_anon = user_identity(request)
        items = await asyncio.to_thread(store.list_for_owner, owner_id, limit)
        return {"success": True, "messages": items}

    @router.get("/api/messages/{message_id}")
    async def read_message(message_id: str, request: Request):
        owner_id, _account_email, _new_anon = user_identity(request)
        item = await asyncio.to_thread(store.get_for_user, message_id, owner_id, token_from(request))
        if not item:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "message": item}

    @router.post("/api/messages/{message_id}/read")
    async def mark_message_read(message_id: str, request: Request):
        owner_id, _account_email, _new_anon = user_identity(request)
        ok = await asyncio.to_thread(store.mark_user_read, message_id, owner_id, token_from(request))
        if not ok:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True}

    @router.get("/api/admin/messages/summary")
    async def admin_summary(request: Request):
        require_admin(request)
        return {"success": True, "summary": await asyncio.to_thread(store.summary)}

    @router.get("/api/admin/messages")
    async def admin_list_messages(
        request: Request,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ):
        require_admin(request)
        if status and status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        if category and category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        items = await asyncio.to_thread(
            store.list_admin,
            status=status,
            category=category,
            search=search,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "messages": items}

    @router.get("/api/admin/messages/{message_id}")
    async def admin_read_message(message_id: str, request: Request):
        require_admin(request)
        item = await asyncio.to_thread(store.get_for_admin, message_id)
        if not item:
            raise HTTPException(status_code=404, detail="Message not found")
        await asyncio.to_thread(store.mark_admin_read, message_id)
        item = await asyncio.to_thread(store.get_for_admin, message_id)
        return {"success": True, "message": item}

    @router.post("/api/admin/messages/{message_id}/reply")
    async def admin_reply(message_id: str, body: AdminReplyCreate, request: Request):
        admin_email = require_admin(request)
        text = body.reply.strip()
        if len(text) < 2:
            raise HTTPException(status_code=400, detail="Please write a reply.")
        message = await asyncio.to_thread(store.get_for_admin, message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        reply = await asyncio.to_thread(
            store.add_reply,
            message_id=message_id,
            reply=text,
            admin_email=admin_email,
            email_requested=body.send_email,
        )
        if not reply:
            raise HTTPException(status_code=404, detail="Message not found")

        if body.send_email:
            email_status, email_error = await asyncio.to_thread(
                send_support_reply,
                to_email=message.get("contact_email"),
                subject=message.get("subject") or "Support message",
                reply=text,
                message_id=message_id,
            )
        else:
            email_status, email_error = "not_requested", None
        await asyncio.to_thread(store.update_reply_delivery, reply["id"], email_status, email_error)
        reply = await asyncio.to_thread(store.get_reply, reply["id"], include_private=True)
        return {
            "success": True,
            "reply": reply,
            "email_status": email_status,
            "email_message": email_error,
        }

    @router.patch("/api/admin/messages/{message_id}/status")
    async def admin_change_status(message_id: str, body: StatusChange, request: Request):
        require_admin(request)
        status = body.status.strip().lower()
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        if not await asyncio.to_thread(store.update_status, message_id, status):
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "status": status}

    @router.post("/api/admin/messages/purge-expired")
    async def admin_purge_expired(request: Request):
        require_admin(request)
        removed = await asyncio.to_thread(store.purge_expired)
        return {"success": True, "removed": removed}

    return router


def delete_messages_for_owners(owner_ids) -> int:
    """Compatibility hook for account/child-data erasure workflows."""
    if _STORE is None:
        return 0
    expanded = []
    for value in owner_ids:
        if value:
            text = str(value)
            expanded.extend([text, f"anonymous:{text}", f"account:{text.lower()}"])
    return _STORE.delete_for_owners(expanded)
