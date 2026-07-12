"""Parent-facing learning-memory API routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .account_store import ensure_account, ensure_default_student, student_belongs_to_account
from .memory_store import get_memory_store
from .runtime import run_blocking


class MemorySettingsRequest(BaseModel):
    enabled: bool
    retention_days: int = Field(default=365, ge=30, le=730)


class MemoryPreferencesRequest(BaseModel):
    explanation_style: str = "short_steps"
    hint_style: str = "one_at_a_time"
    accessibility: Dict[str, Any] = Field(default_factory=dict)


class TopicDeleteRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=80)


def build_memory_router(resolve_username):
    router = APIRouter(prefix="/api/memory", tags=["learning-memory"])

    async def owned_context(request: Request, student_id: str):
        username = resolve_username(request)
        if not username:
            raise HTTPException(status_code=401, detail="A parent or guardian must sign in.")
        account = await run_blocking(ensure_account, username, limit_concurrency=False)
        await run_blocking(ensure_default_student, account["id"], limit_concurrency=False)
        belongs = await run_blocking(
            student_belongs_to_account, student_id, account["id"], limit_concurrency=False
        )
        if not belongs:
            raise HTTPException(status_code=404, detail="Learner profile not found.")
        return account

    @router.get("/{student_id}")
    async def memory_summary(student_id: str, request: Request):
        account = await owned_context(request, student_id)
        data = await run_blocking(
            get_memory_store().summary, student_id, account["id"], limit_concurrency=False
        )
        return {"success": True, "memory": data}

    @router.put("/{student_id}/settings")
    async def memory_settings(student_id: str, body: MemorySettingsRequest, request: Request):
        account = await owned_context(request, student_id)
        settings = await run_blocking(
            get_memory_store().update_settings,
            student_id,
            account["id"],
            enabled=body.enabled,
            retention_days=body.retention_days,
            limit_concurrency=False,
        )
        return {
            "success": True,
            "settings": settings,
            "message": (
                "Learning memory is on. Only structured learning progress will be remembered."
                if body.enabled
                else "Learning memory is off. No new learning events will be remembered."
            ),
        }

    @router.put("/{student_id}/preferences")
    async def memory_preferences(student_id: str, body: MemoryPreferencesRequest, request: Request):
        account = await owned_context(request, student_id)
        preferences = await run_blocking(
            get_memory_store().update_preferences,
            student_id,
            account["id"],
            explanation_style=body.explanation_style,
            hint_style=body.hint_style,
            accessibility=body.accessibility,
            limit_concurrency=False,
        )
        return {"success": True, "preferences": preferences}

    @router.delete("/{student_id}")
    async def clear_memory(
        student_id: str,
        request: Request,
        include_preferences: bool = False,
    ):
        account = await owned_context(request, student_id)
        deleted = await run_blocking(
            get_memory_store().delete_all,
            student_id,
            account["id"],
            include_preferences=include_preferences,
            limit_concurrency=False,
        )
        return {"success": True, "deleted_events": deleted}

    @router.post("/{student_id}/delete-topic")
    async def clear_topic(student_id: str, body: TopicDeleteRequest, request: Request):
        account = await owned_context(request, student_id)
        deleted = await run_blocking(
            get_memory_store().delete_topic,
            student_id,
            account["id"],
            body.subject,
            body.topic,
            limit_concurrency=False,
        )
        return {"success": True, "deleted_events": deleted}

    @router.get("/{student_id}/export")
    async def export_memory(student_id: str, request: Request):
        account = await owned_context(request, student_id)
        data = await run_blocking(
            get_memory_store().export, student_id, account["id"], limit_concurrency=False
        )
        return {"success": True, "memory_export": data}

    return router
