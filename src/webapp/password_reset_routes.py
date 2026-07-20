"""Forgot-password pages and API routes."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .email_service import password_reset_email_configuration_issues, send_password_reset_email
from .password_backend import PasswordBackendError, account_exists, revoke_account_sessions, set_account_password
from .password_reset_store import PasswordResetStore

logger = logging.getLogger(__name__)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_GENERIC_MESSAGE = "If an account matches that email, a password reset link has been sent."
_EMAIL_UNAVAILABLE_MESSAGE = (
    "Password reset email is temporarily unavailable. Please try again later or contact support."
)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=10, max_length=128)
    confirm_password: str = Field(min_length=10, max_length=128)


def _page(project_root: str, filename: str) -> FileResponse:
    path = Path(project_root) / "static" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(
        str(path),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )


def _normalise_email(value: str) -> str:
    email = value.strip().lower()
    if not _EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    return email


def _client_hash(request: Request) -> str:
    raw = request.client.host if request.client else "unknown"
    secret = (
        os.getenv("PASSWORD_RESET_RATE_LIMIT_SECRET")
        or os.getenv("SESSION_SECRET")
        or os.getenv("AUTH_SECRET")
        or "development-password-reset-secret"
    )
    return hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _base_url(request: Request) -> str:
    configured = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    return configured or str(request.base_url).rstrip("/")


def _valid_password(password: str) -> bool:
    # Long passwords are supported; no special-character puzzle is imposed.
    return 10 <= len(password) <= 128 and not password.isspace()


def create_password_reset_router(*, project_root: str, dev_mode: bool = False) -> APIRouter:
    store = PasswordResetStore(project_root)
    store.purge_expired()
    router = APIRouter()

    @router.get("/forgot-password")
    async def forgot_password_page():
        return _page(project_root, "forgot-password.html")

    @router.get("/reset-password")
    async def reset_password_page():
        return _page(project_root, "reset-password.html")

    @router.post("/api/password-reset/request")
    async def request_password_reset(body: PasswordResetRequest, request: Request):
        email = _normalise_email(body.email)
        email_issues = password_reset_email_configuration_issues()
        show_dev_link = (
            dev_mode
            and os.getenv("PASSWORD_RESET_DEV_SHOW_LINK", "").lower() in {"1", "true", "yes"}
        )
        # Configuration availability is account-independent, so reporting it
        # does not reveal whether the submitted email address is registered.
        if email_issues and not show_dev_link:
            logger.error("Password reset email is unavailable: %s", "; ".join(email_issues))
            return JSONResponse(
                status_code=503,
                content={"success": False, "detail": _EMAIL_UNAVAILABLE_MESSAGE},
            )

        allowed = await asyncio.to_thread(store.record_request_if_allowed, email, _client_hash(request))
        # Rate limiting uses the same public response to avoid account discovery.
        if not allowed:
            return JSONResponse({"success": True, "message": _GENERIC_MESSAGE}, headers={"Retry-After": "3600"})

        exists = False
        try:
            exists = await asyncio.to_thread(account_exists, email)
        except Exception:
            logger.exception("Password reset account lookup failed")

        dev_reset_url = None
        if exists:
            token, _expires = await asyncio.to_thread(store.create_token, email)
            reset_url = f"{_base_url(request)}/reset-password?{urlencode({'token': token})}"
            if not email_issues:
                status, error = await asyncio.to_thread(
                    send_password_reset_email,
                    to_email=email,
                    reset_url=reset_url,
                    expires_minutes=store.token_minutes,
                )
                if status != "sent":
                    logger.warning(
                        "Password reset email was not sent (status=%s, reason=%s)",
                        status,
                        error or "unknown",
                    )
            if show_dev_link:
                dev_reset_url = reset_url

        payload = {"success": True, "message": _GENERIC_MESSAGE}
        if dev_reset_url:
            payload["dev_reset_url"] = dev_reset_url
        return payload

    @router.get("/api/password-reset/validate")
    async def validate_password_reset(token: str = ""):
        valid = await asyncio.to_thread(store.is_valid, token)
        return {"success": True, "valid": valid}

    @router.post("/api/password-reset/confirm")
    async def confirm_password_reset(body: PasswordResetConfirm):
        if body.password != body.confirm_password:
            raise HTTPException(status_code=400, detail="The passwords do not match.")
        if not _valid_password(body.password):
            raise HTTPException(status_code=400, detail="Use a password with at least 10 characters.")

        email = await asyncio.to_thread(store.consume, body.token)
        if not email:
            raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Please request a new one.")
        try:
            updated = await asyncio.to_thread(set_account_password, email, body.password)
        except PasswordBackendError:
            logger.exception("Password backend is not configured for resets")
            raise HTTPException(status_code=500, detail="Your password could not be changed. Please request a new link or contact support.")
        except Exception:
            logger.exception("Password reset failed")
            raise HTTPException(status_code=500, detail="Your password could not be changed. Please request a new link or contact support.")
        if not updated:
            raise HTTPException(status_code=400, detail="This reset link cannot be used. Please request a new one.")

        await asyncio.to_thread(revoke_account_sessions, email)
        response = JSONResponse({"success": True, "message": "Your password has been changed. You can now log in."})
        response.delete_cookie("session", httponly=True, samesite="lax", secure=not dev_mode)
        return response

    return router
