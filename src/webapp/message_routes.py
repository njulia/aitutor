"""FastAPI router for user messages and admin replies."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .email_service import send_support_reply
from .message_models import AdminMessageReplyRequest, AdminMessageStatusRequest, UserMessageCreateRequest
from .message_store import MessageStore


def create_message_router(
    *,
    resolve_identity: Callable[[Request], tuple[str, Optional[str], Optional[str]]],
    project_root: str,
    store: Optional[MessageStore] = None,
) -> APIRouter:
    router = APIRouter()
    message_store = store or MessageStore()
    static_root = Path(project_root) / "static"

    def require_admin(request: Request) -> None:
        configured = os.getenv("ADMIN_API_KEY", "").strip()
        if configured and request.headers.get("X-Admin-Key") != configured:
            raise HTTPException(status_code=403, detail="Admin access denied")

    def logged_in_email(request: Request) -> Optional[str]:
        _user_id, username, _cookie = resolve_identity(request)
        return username.lower() if username else None

    @router.get("/messages")
    async def messages_page():
        return FileResponse(static_root / "messages.html")

    @router.get("/admin/messages")
    async def admin_messages_page():
        return FileResponse(static_root / "admin-messages.html")

    @router.post("/api/messages")
    async def create_message(request: Request, body: UserMessageCreateRequest):
        user_id, username, new_cookie = resolve_identity(request)
        email = (username or (str(body.email) if body.email else "")).strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email is required for anonymous messages")
        result = message_store.create_message(
            user_id=None if user_id.startswith("anon_") else user_id,
            user_email=email,
            subject=body.subject,
            category=body.category,
            message=body.message,
        )
        response = JSONResponse({"success": True, "message": result})
        if new_cookie:
            response.set_cookie("anon_session_id", new_cookie, httponly=True, samesite="lax")
        return response

    @router.get("/api/messages")
    async def list_my_messages(request: Request, access_token: Optional[str] = None, email: Optional[str] = None):
        account_email = logged_in_email(request)
        lookup_email = account_email or (email or "").strip().lower()
        if not lookup_email and not access_token:
            raise HTTPException(status_code=401, detail="Login, email or access token required")
        items = message_store.list_for_user(email=lookup_email, access_token=access_token)
        return {"success": True, "messages": items}

    @router.get("/api/messages/{message_id}")
    async def get_my_message(request: Request, message_id: int, access_token: Optional[str] = None):
        item = message_store.get_for_user(
            message_id,
            email=logged_in_email(request),
            access_token=access_token,
        )
        if not item:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "message": item}

    @router.get("/api/admin/messages")
    async def admin_list_messages(
        request: Request,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ):
        require_admin(request)
        return {"success": True, "messages": message_store.list_admin(status=status, limit=min(limit, 500), offset=offset)}

    @router.get("/api/admin/messages/{message_id}")
    async def admin_get_message(request: Request, message_id: int):
        require_admin(request)
        item = message_store.get_message(message_id)
        if not item:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "message": item}

    @router.post("/api/admin/messages/{message_id}/reply")
    async def admin_reply(request: Request, message_id: int, body: AdminMessageReplyRequest):
        require_admin(request)
        item = message_store.get_message(message_id)
        if not item:
            raise HTTPException(status_code=404, detail="Message not found")

        email_status, email_error = ("not_requested", None)
        if body.send_email:
            email_status, email_error = send_support_reply(
                recipient=item["user_email"],
                original_subject=item["subject"],
                original_message=item["message"],
                reply=body.reply,
                admin_name=body.admin_name,
            )

        updated = message_store.add_reply(
            message_id=message_id,
            admin_name=body.admin_name,
            reply=body.reply,
            email_status=email_status,
            email_error=email_error,
        )
        return {
            "success": True,
            "message": updated,
            "email_status": email_status,
            "email_error": email_error,
        }

    @router.patch("/api/admin/messages/{message_id}/status")
    async def admin_update_status(request: Request, message_id: int, body: AdminMessageStatusRequest):
        require_admin(request)
        updated = message_store.update_status(message_id, body.status)
        if not updated:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "message": updated}

    return router
