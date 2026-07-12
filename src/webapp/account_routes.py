"""Non-blocking FastAPI routes for accounts and students."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Request, Response

from pydantic import BaseModel

from .account_models import AccountSubscriptionRequest, StudentCreateRequest, StudentUpdateRequest
from .privacy_service import erase_account, erase_learner


class AccountDeleteRequest(BaseModel):
    confirmation: str
from .account_store import (
    create_student,
    create_subscription,
    ensure_account,
    ensure_default_student,
    get_account_overview,
    list_students,
    student_belongs_to_account,
    update_student,
)


def build_account_router(resolve_username, require_admin, session_store):
    router = APIRouter(prefix="/api")

    async def current_account(request: Request):
        username = resolve_username(request)
        if not username:
            raise HTTPException(status_code=401, detail="Login required")
        account = await asyncio.to_thread(ensure_account, username)
        await asyncio.to_thread(ensure_default_student, account["id"])
        return account

    @router.get("/account")
    async def account_detail(request: Request):
        account = await current_account(request)
        overview = await asyncio.to_thread(get_account_overview, account["email"])
        return {"success": True, **overview}

    @router.get("/students")
    async def students(request: Request):
        account = await current_account(request)
        items = await asyncio.to_thread(list_students, account["id"])
        return {"success": True, "students": items}

    @router.post("/students")
    async def add_student(request: Request, body: StudentCreateRequest):
        account = await current_account(request)
        try:
            student = await asyncio.to_thread(
                create_student, account["id"], body.name, body.year_group, body.age
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"success": True, "student": student}

    @router.put("/students/{student_id}")
    async def edit_student(student_id: str, request: Request, body: StudentUpdateRequest):
        account = await current_account(request)
        belongs = await asyncio.to_thread(student_belongs_to_account, student_id, account["id"])
        if not belongs:
            raise HTTPException(status_code=404, detail="Student not found")
        try:
            student = await asyncio.to_thread(
                update_student,
                student_id,
                account["id"],
                **body.model_dump(exclude_unset=True),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"success": True, "student": student}

    @router.delete("/students/{student_id}")
    async def remove_student(student_id: str, request: Request):
        account = await current_account(request)
        belongs = await asyncio.to_thread(student_belongs_to_account, student_id, account["id"])
        if not belongs:
            raise HTTPException(status_code=404, detail="Learner profile not found")
        remaining = await asyncio.to_thread(list_students, account["id"], True)
        if len(remaining) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Create another learner profile before deleting the only profile, or delete the whole account.",
            )
        result = await asyncio.to_thread(
            erase_learner,
            account_id=account["id"],
            student_id=student_id,
            account_email=account["email"],
            session_store=session_store,
        )
        return {"success": True, "erasure": result}

    @router.delete("/account")
    async def remove_account(body: AccountDeleteRequest, request: Request, response: Response):
        if body.confirmation != "DELETE":
            raise HTTPException(status_code=400, detail="Type DELETE to confirm account erasure")
        account = await current_account(request)
        try:
            result = await asyncio.to_thread(
                erase_account,
                account_id=account["id"],
                account_email=account["email"],
                session_store=session_store,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        response.delete_cookie("session")
        response.delete_cookie("anon_session_id")
        return {"success": True, "erasure": result}

    @router.post("/admin/account-subscriptions")
    async def admin_add_subscription(request: Request, body: AccountSubscriptionRequest):
        require_admin(request)
        import os
        if os.getenv("DEV_MODE", "").lower() not in {"1", "true", "yes"}:
            raise HTTPException(
                status_code=410,
                detail="Manual subscriptions are disabled in production. Use Stripe Checkout and verified webhooks.",
            )
        account = await asyncio.to_thread(ensure_account, body.email)
        sub = await asyncio.to_thread(
            create_subscription,
            account["id"],
            body.plan,
            body.status,
            body.duration_days,
            body.stripe_customer_id,
            body.stripe_subscription_id,
        )
        return {"success": True, "account": account, "subscription": sub}

    @router.get("/admin/accounts/{email}")
    async def admin_account(email: str, request: Request):
        require_admin(request)
        overview = await asyncio.to_thread(get_account_overview, email)
        return {"success": True, **overview}

    return router
