"""家长仪表盘路由：查看孩子进度、设置学习目标、管理奖励目录。"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr

from src.progress_db import verify_user_credentials

from .account_store import (
    ensure_account,
    get_learning_target,
    list_students,
    set_learning_target,
    student_belongs_to_account,
)
from .reward_store import get_reward_store


logger = logging.getLogger(__name__)


class LearningTargetRequest(BaseModel):
    student_id: str = Field(..., max_length=80)
    daily_goal: int = Field(default=1, ge=1, le=10)
    weekly_xp_goal: int = Field(default=100, ge=10, le=2000)
    focus_subjects: Optional[str] = Field(default=None, max_length=200)
    parent_password: SecretStr


class XpDigestRequest(BaseModel):
    parent_password: SecretStr


def build_parent_dashboard_router(resolve_username) -> APIRouter:
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
            list_students, account["id"]
        )
        kids = []
        for student in students:
            target = await asyncio.to_thread(
                get_learning_target, student["id"]
            )
            # 获取孩子的 XP 数据
            try:
                dashboard = await asyncio.to_thread(
                    get_reward_store().dashboard,
                    account_id=account["id"],
                    student_id=student["id"],
                )
                wallet = dashboard.get("wallet", {})
            except Exception:
                wallet = {"lifetime_xp": 0, "gift_points": 0}
            kids.append({
                "id": student["id"],
                "name": student["name"],
                "year_group": student["year_group"],
                "age": student["age"],
                "kid_code": student.get("kid_code"),
                "learning_target": target,
                "wallet": wallet,
            })
        return {
            "success": True,
            "family_code": account.get("family_code"),
            "kids": kids,
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
        """获取家庭过去 24 小时的 XP 收益摘要。"""
        account = await account_context(request)
        digest = await asyncio.to_thread(
            get_reward_store().get_xp_digest_for_account,
            account_id=account["id"],
        )
        # 附加孩子名字
        students = await asyncio.to_thread(
            list_students, account["id"]
        )
        name_map = {s["id"]: s["name"] for s in students}
        for kid in digest.get("kids", []):
            kid["name"] = name_map.get(kid["student_id"], "Unknown")
        return {"success": True, "digest": digest}

    @router.post("/api/parent/xp-digest/send")
    async def send_xp_digest_email(request: Request, body: XpDigestRequest):
        """家长手动触发发送 XP 摘要邮件。"""
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        digest = await asyncio.to_thread(
            get_reward_store().get_xp_digest_for_account,
            account_id=account["id"],
        )
        # 附加孩子名字
        students = await asyncio.to_thread(
            list_students, account["id"]
        )
        name_map = {s["id"]: s["name"] for s in students}
        for kid in digest.get("kids", []):
            kid["name"] = name_map.get(kid["student_id"], "Unknown")
        # 发送邮件
        from .email_service import send_xp_digest_email
        try:
            await asyncio.to_thread(
                send_xp_digest_email,
                to_email=account["email"],
                digest=digest,
            )
        except Exception:
            logger.exception("Failed to send XP digest email")
            raise HTTPException(
                status_code=503,
                detail="Could not send the email just now. Please try again.",
            )
        return {"success": True, "message": "Digest email sent"}

    return router
