"""家长仪表盘路由：查看孩子进度、设置学习目标、管理奖励目录。"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr

from src.progress_db import (
    get_mock_study_plan,
    get_progress_summary,
    get_streak_info,
    get_students_subject_breakdown,
    verify_user_credentials,
)

from .account_store import (
    adjust_student_for_academic_year,
    ensure_account,
    get_learning_target,
    get_student_limit,
    get_student,
    get_account,
    list_students,
    set_learning_target,
    student_belongs_to_account,
    get_learning_summary_preferences,
    set_learning_summary_preferences,
    claim_learning_summary_target_notification,
    release_learning_summary_target_notification,
    list_due_learning_summary_accounts,
    mark_learning_summary_sent,
)
from .reward_store import get_reward_store
from .runtime import is_30_day_study_plan_enabled


def _utcnow() -> datetime:
    """返回当前UTC时间。"""
    return datetime.now(tz=UTC)


logger = logging.getLogger(__name__)


class LearningTargetRequest(BaseModel):
    student_id: str = Field(..., max_length=80)
    daily_goal: int = Field(default=1, ge=1, le=10)
    weekly_xp_goal: int = Field(default=100, ge=10, le=2000)
    focus_subjects: Optional[str] = Field(default=None, max_length=200)
    parent_password: SecretStr


class XpDigestRequest(BaseModel):
    parent_password: SecretStr


class LearningSummaryPreferencesRequest(BaseModel):
    enabled: bool = True
    frequency: str = Field(default="weekly", pattern="^(custom|weekly|monthly|yearly)$")
    interval_days: int = Field(default=7, ge=1, le=365)


class GiftRequestDecision(BaseModel):
    parent_password: SecretStr
    xp_to_deduct: int | None = Field(default=None, ge=0, le=5000)


def build_learning_summary_digest(account_id: str, since: datetime | None = None) -> dict:
    """Build exactly the four columns shown in the parent Learning summary."""
    store = get_reward_store()
    digest = store.get_xp_digest_for_account(account_id=account_id, since=since)
    students = list_students(account_id)
    name_map = {s["id"]: s["name"] for s in students}
    kid_ids = [k["student_id"] for k in digest.get("kids", [])]
    subject_breakdown = get_students_subject_breakdown(student_ids=kid_ids, since=since) if kid_ids else {}
    if kid_ids and not any(subject_breakdown.values()):
        subject_breakdown = get_students_subject_breakdown(
            student_ids=kid_ids, since=_utcnow() - timedelta(days=7)
        )
    for kid in digest.get("kids", []):
        sid = kid["student_id"]
        kid["name"] = name_map.get(sid, "Unknown")
        kid["subjects"] = subject_breakdown.get(sid, [])
    return digest


def send_target_learning_summary_if_reached(account_id: str, student_id: str) -> None:
    """Send one Learning summary when a child first meets today's daily goal."""
    preferences = get_learning_summary_preferences(account_id)
    if not preferences.get("enabled"):
        return
    target = get_learning_target(student_id)
    daily_goal = max(1, int(target.get("daily_goal") or 1))
    local_day = datetime.now(ZoneInfo(os.getenv("REWARD_TIMEZONE") or "Europe/London")).date().isoformat()
    today_count = get_reward_store().get_daily_activity_count(
        student_id=student_id, local_day=local_day
    )
    if today_count < daily_goal:
        return
    if not claim_learning_summary_target_notification(account_id, student_id, local_day):
        return
    digest = build_learning_summary_digest(account_id)
    if not digest.get("kids"):
        return
    from .email_service import send_xp_digest_email
    status, error = send_xp_digest_email(to_email=get_account(account_id).get("email", ""), digest=digest)
    if status != "sent":
        release_learning_summary_target_notification(account_id, student_id, local_day)
        logger.warning("Target learning summary email was not sent: %s", error or status)


def send_due_learning_summaries() -> dict:
    """Send scheduled summaries; intended to be called by Cloud Scheduler."""
    sent = skipped = failed = 0
    from .email_service import send_xp_digest_email
    now = _utcnow()
    for preference in list_due_learning_summary_accounts(now):
        account_id = preference["account_id"]
        last_sent = preference.get("last_sent_at")
        since = last_sent if isinstance(last_sent, datetime) else now - timedelta(days=max(1, int(preference.get("interval_days") or 7)))
        digest = build_learning_summary_digest(account_id, since=since)
        if not digest.get("kids"):
            mark_learning_summary_sent(account_id, now)
            skipped += 1
            continue
        status, _error = send_xp_digest_email(to_email=preference["email"], digest=digest)
        if status == "sent":
            mark_learning_summary_sent(account_id, now)
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "skipped": skipped, "failed": failed}


def build_parent_dashboard_router(resolve_username, has_subscription=None) -> APIRouter:
    router = APIRouter()

    async def account_context(request: Request) -> dict:
        username = resolve_username(request)
        if not username:
            raise HTTPException(
                status_code=401,
                detail="A parent or guardian needs to sign in.",
            )
        return await asyncio.to_thread(ensure_account, username)

    async def confirm_parent(account: dict, password: str) -> None:
        valid = await asyncio.to_thread(
            verify_user_credentials, account["email"], password
        )
        if not valid:
            raise HTTPException(
                status_code=403,
                detail="The parent account password did not match.",
            )

    @router.get("/api/parent/overview")
    async def parent_overview(request: Request):
        """家长查看家庭概览：所有孩子及其学习进度。"""
        account = await account_context(request)
        students = await asyncio.to_thread(
            list_students, account["id"], True
        )

        async def kid_overview(student: dict) -> dict:
            adjusted = adjust_student_for_academic_year(student)
            try:
                target, progress, streak, wallet = await asyncio.gather(
                    asyncio.to_thread(get_learning_target, adjusted["id"]),
                    asyncio.to_thread(get_progress_summary, adjusted["id"]),
                    asyncio.to_thread(get_streak_info, adjusted["id"]),
                    asyncio.to_thread(
                        get_reward_store().learner_summary,
                        account_id=account["id"],
                        student_id=adjusted["id"],
                    ),
                )
            except Exception:
                logger.exception("Could not load learner overview")
                target = await asyncio.to_thread(
                    get_learning_target, adjusted["id"]
                )
                progress = {"total_sessions": 0, "average_accuracy": 0}
                streak = {"current_streak": 0}
                wallet = {
                    "lifetime_xp": 0,
                    "gift_points": 0,
                    "level": {"number": 1, "name": "Starter", "icon": "🌱"},
                    "pending_rewards": 0,
                }
            return {
                "id": adjusted["id"],
                "name": adjusted["name"],
                "year_group": adjusted["year_group"],
                "age": adjusted["age"],
                "is_default": bool(adjusted.get("is_default")),
                "kid_code": adjusted.get("kid_code"),
                "learning_target": target,
                "wallet": wallet,
                "progress": {
                    "total_sessions": int(progress.get("total_sessions") or 0),
                    "average_accuracy": float(progress.get("average_accuracy") or 0),
                    "current_streak": int(streak.get("current_streak") or 0),
                    "score_history": [
                        {
                            "subject": str(item.get("subject") or ""),
                            "score": float(item.get("score") or 0),
                            "max_score": float(item.get("max_score") or 0),
                            "created_at": item.get("created_at"),
                        }
                        for item in (progress.get("score_history") or [])
                    ],
                },
            }

        kids, student_limit = await asyncio.gather(
            asyncio.gather(*(kid_overview(student) for student in students)),
            asyncio.to_thread(get_student_limit, account["id"]),
        )
        return {
            "success": True,
            "study_plan_enabled": is_30_day_study_plan_enabled(),
            "family_code": account.get("family_code"),
            "kids": list(kids),
            "student_limit": int(student_limit),
            "can_add_student": len(students) < int(student_limit),
        }

    @router.get("/api/parent/11plus-study-plan/{student_id}")
    async def get_11plus_study_plan(request: Request, student_id: str):
        """Return a learner's latest 30-day 11+ plan to a subscribed parent."""
        if not is_30_day_study_plan_enabled():
            raise HTTPException(status_code=404, detail="The 30-day study plan is currently disabled.")
        account = await account_context(request)
        belongs = await asyncio.to_thread(
            student_belongs_to_account, student_id, account["id"]
        )
        if not belongs:
            raise HTTPException(status_code=404, detail="Learner profile not found")
        if has_subscription is None:
            raise HTTPException(status_code=402, detail="11+ Premium is required to view this study plan.")
        try:
            allowed = await asyncio.to_thread(
                has_subscription,
                request,
                None,
                account["email"],
                "elevenplus_monthly",
                True,
            )
        except Exception:
            logger.exception("Could not check 11+ Premium for study plan")
            allowed = False
        if not allowed:
            return {
                "success": False,
                "locked": True,
                "required_plan": "elevenplus_monthly",
                "required_plan_name": "11+ Premium",
                "pricing_url": "/pricing",
            }
        plan = await asyncio.to_thread(get_mock_study_plan, student_id)
        return {
            "success": True,
            "locked": False,
            "plan": plan,
            "ready": bool(plan),
        }

    @router.get("/api/parent/learning-target/{student_id}")
    async def get_target(request: Request, student_id: str):
        """获取某孩子的学习目标。"""
        account = await account_context(request)
        belongs = await asyncio.to_thread(
            student_belongs_to_account, student_id, account["id"]
        )
        if not belongs:
            raise HTTPException(status_code=404, detail="Learner profile not found")
        target = await asyncio.to_thread(get_learning_target, student_id)
        return {"success": True, "target": target}

    @router.post("/api/parent/learning-target")
    async def set_target(request: Request, body: LearningTargetRequest):
        """家长为孩子设置学习目标。"""
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        belongs = await asyncio.to_thread(
            student_belongs_to_account, body.student_id, account["id"]
        )
        if not belongs:
            raise HTTPException(status_code=404, detail="Learner profile not found")
        target = await asyncio.to_thread(
            set_learning_target,
            account["id"],
            body.student_id,
            daily_goal=body.daily_goal,
            weekly_xp_goal=body.weekly_xp_goal,
            focus_subjects=body.focus_subjects,
        )
        return {"success": True, "target": target}

    @router.get("/api/parent/xp-digest")
    async def get_xp_digest(request: Request):
        account = await account_context(request)
        digest = await asyncio.to_thread(build_learning_summary_digest, account["id"])
        return {"success": True, "digest": digest}

    @router.post("/api/parent/xp-digest/send")
    async def send_xp_digest_email_route(request: Request, body: XpDigestRequest):
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        digest = await asyncio.to_thread(build_learning_summary_digest, account["id"])
        if not digest.get("kids"):
            raise HTTPException(status_code=409, detail="There is no recent learning activity to email yet.")
        from .email_service import send_xp_digest_email
        status, error = await asyncio.to_thread(send_xp_digest_email, to_email=account["email"], digest=digest)
        if status != "sent":
            raise HTTPException(status_code=503, detail=error or "Could not send the email just now. Please try again.")
        return {"success": True, "message": "Digest email sent"}

    @router.get("/api/parent/learning-summary/preferences")
    async def learning_summary_preferences(request: Request):
        account = await account_context(request)
        preferences = await asyncio.to_thread(get_learning_summary_preferences, account["id"])
        return {"success": True, "preferences": preferences}

    @router.put("/api/parent/learning-summary/preferences")
    async def update_learning_summary_preferences(request: Request, body: LearningSummaryPreferencesRequest):
        account = await account_context(request)
        preferences = await asyncio.to_thread(
            set_learning_summary_preferences, account["id"], enabled=body.enabled,
            frequency=body.frequency, interval_days=body.interval_days
        )
        return {"success": True, "preferences": preferences}

    @router.post("/api/internal/learning-summary/send-due")
    async def send_due_learning_summary_endpoint(request: Request):
        configured = (os.getenv("LEARNING_SUMMARY_CRON_TOKEN") or "").strip()
        supplied = (request.headers.get("X-Learning-Summary-Token") or "").strip()
        if not configured or not supplied or not secrets.compare_digest(configured, supplied):
            raise HTTPException(status_code=403, detail="Not authorised")
        result = await asyncio.to_thread(send_due_learning_summaries)
        return {"success": True, **result}

    @router.get("/api/parent/gift-requests")
    async def list_gift_requests(request: Request):
        """家长查看待审批的礼物请求列表。"""
        account = await account_context(request)
        requests = await asyncio.to_thread(
            get_reward_store().get_pending_redemptions_for_account,
            account_id=account["id"],
        )
        return {"success": True, "requests": requests}

    @router.post("/api/parent/gift-requests/{redemption_id}/approve")
    async def approve_gift_request(
        redemption_id: str,
        request: Request,
        body: GiftRequestDecision,
    ):
        """家长同意礼物请求，扣除 Gift Points。"""
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        try:
            result = await asyncio.to_thread(
                get_reward_store().decide_redemption_with_custom_xp,
                account_id=account["id"],
                redemption_id=redemption_id,
                decision="approve",
                xp_to_deduct=body.xp_to_deduct,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"success": True, **result}

    @router.post("/api/parent/gift-requests/{redemption_id}/decline")
    async def decline_gift_request(
        redemption_id: str,
        request: Request,
        body: GiftRequestDecision,
    ):
        """家长拒绝礼物请求，不扣除点数。"""
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        try:
            result = await asyncio.to_thread(
                get_reward_store().decide_redemption_with_custom_xp,
                account_id=account["id"],
                redemption_id=redemption_id,
                decision="decline",
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"success": True, **result}

    return router
