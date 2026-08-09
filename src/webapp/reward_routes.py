"""Authenticated learner rewards and parent-approved gift routes."""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, SecretStr

from src.progress_db import verify_user_credentials

from .account_store import (
    account_has_active_reward_subscription,
    ensure_account,
    ensure_default_student,
    get_account,
    get_student,
    student_belongs_to_account,
)
from .reward_models import (
    AdminGiftOrderDecisionRequest,
    CustomRewardRequest,
    RewardDecisionRequest,
    RewardRequest,
)
from .reward_store import get_reward_store


logger = logging.getLogger(__name__)
GIFT_ACCESS_NOTE = (
    "Everyone can earn XP. A grown-up manages Gift Points, gifts and plans."
)
PARENT_GIFT_PLAN_NOTE = (
    "Gift Points are available to all registered families. "
    "A grown-up manages gift approvals and delivery."
)


def _avatar_age_context(learner: dict) -> dict[str, int]:
    """Return only the learner fields needed for age-based avatar proportions."""
    age = max(5, min(11, int(learner.get("age") or 7)))
    year_group = max(1, min(6, int(learner.get("year_group") or age - 5)))
    return {"age": age, "year_group": year_group}


class CatalogItemRequest(BaseModel):
    name: str = Field(default="", max_length=40)
    icon: str = Field(default="gift", max_length=12)
    xp_cost: int = Field(default=100, ge=10, le=5000)
    parent_password: SecretStr


class CatalogItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=40)
    icon: str | None = Field(default=None, max_length=12)
    xp_cost: int | None = Field(default=None, ge=10, le=5000)
    is_active: bool | None = None
    parent_password: SecretStr


class ParentRedemptionDecisionRequest(BaseModel):
    decision: str
    xp_to_deduct: int | None = Field(default=None, ge=0, le=5000)
    parent_password: SecretStr


class ParentPasswordRequest(BaseModel):
    parent_password: SecretStr


class AvatarPreferenceRequest(BaseModel):
    student_id: str | None = Field(default=None, max_length=80)
    character: str = Field(default="girl", max_length=20)
    clothes: str = Field(default="pink_dress", max_length=30)
    bottoms: str = Field(default="match_outfit", max_length=30)
    shoes: str = Field(default="trainers", max_length=30)
    skin_tone: str = Field(default="warm", max_length=20)
    hair_colour: str = Field(default="brown", max_length=20)
    hair_length: str = Field(default="long", max_length=20)
    hair_style: str = Field(default="ponytail", max_length=20)
    eye_shape: str = Field(default="round", max_length=20)
    eye_colour: str = Field(default="green", max_length=20)
    nose: str = Field(default="button", max_length=20)
    mouth: str = Field(default="smile", max_length=20)
    eyebrows: str = Field(default="arched", max_length=20)


def build_reward_router(
    resolve_username,
    require_admin=None,
    project_root: str | None = None,
) -> APIRouter:
    router = APIRouter()

    def admin_context(request: Request) -> str:
        if require_admin is None:
            raise HTTPException(status_code=403, detail="Admin access denied")
        return require_admin(request)

    async def account_context(request: Request) -> dict:
        username = resolve_username(request)
        if not username:
            raise HTTPException(
                status_code=401,
                detail="A parent or guardian needs to sign in.",
            )
        return await asyncio.to_thread(ensure_account, username)

    async def learner_context(
        request: Request, student_id: str | None
    ) -> tuple[dict, dict]:
        account = await account_context(request)
        if student_id:
            belongs = await asyncio.to_thread(
                student_belongs_to_account, student_id, account["id"]
            )
            if not belongs:
                raise HTTPException(status_code=404, detail="Learner profile not found")
            learner = await asyncio.to_thread(get_student, student_id)
        else:
            learner = await asyncio.to_thread(ensure_default_student, account["id"])
        if not learner:
            raise HTTPException(status_code=404, detail="Learner profile not found")
        return account, learner

    async def gift_points_eligible(account: dict) -> bool:
        try:
            return bool(
                await asyncio.to_thread(
                    account_has_active_reward_subscription,
                    account["id"],
                )
            )
        except Exception:
            # Subscription uncertainty must lock physical gifts without hiding
            # XP, quests or certificates from the learner.
            logger.exception("Could not check reward gift subscription")
            return False

    async def confirm_parent(account: dict, password: str) -> None:
        valid = await asyncio.to_thread(
            verify_user_credentials, account["email"], password
        )
        if not valid:
            raise HTTPException(
                status_code=403,
                detail="The parent account password did not match.",
            )

    async def _resolve_kid_learner(request: Request) -> tuple[dict, dict] | None:
        """尝试解析孩子登录会话，返回 (account, learner) 或 None。"""
        kid_token = request.cookies.get("kid_session") or request.headers.get("X-Kid-Session")
        if not kid_token:
            return None
        from .kid_session_store import resolve_kid_session
        kid_session = await asyncio.to_thread(resolve_kid_session, kid_token)
        if not kid_session:
            return None
        kid_student_id = str(kid_session["student_id"])
        learner = await asyncio.to_thread(get_student, kid_student_id)
        if not learner:
            return None
        account = await asyncio.to_thread(get_account, str(learner["account_id"]))
        if not account:
            return None
        return account, learner

    async def authenticated_learner_context(
        request: Request, student_id: str | None
    ) -> tuple[dict, dict]:
        """Resolve one learner, with a valid kid session taking precedence.

        A kid can only access their own rewards even if a stale parent cookie
        remains in the browser. Parents can select any active learner belonging
        to their family account.
        """
        kid_result = await _resolve_kid_learner(request)
        if kid_result is not None:
            account, learner = kid_result
            if student_id and str(student_id) != str(learner["id"]):
                raise HTTPException(
                    status_code=403,
                    detail="You can only view or request rewards for yourself.",
                )
            return account, learner
        return await learner_context(request, student_id)

    @router.get("/api/rewards")
    async def reward_dashboard(
        request: Request,
        student_id: str | None = Query(default=None, max_length=80),
    ):
        account, learner = await authenticated_learner_context(request, student_id)
        dashboard, eligible = await asyncio.gather(
            asyncio.to_thread(
                get_reward_store().dashboard,
                account_id=account["id"],
                student_id=learner["id"],
            ),
            gift_points_eligible(account),
        )
        return {
            "success": True,
            "learner": {
                "id": learner["id"],
                "name": learner["name"],
                "age": learner["age"],
                "year_group": learner["year_group"],
            },
            "gift_access": {
                "eligible": eligible,
                "requires_active_subscription": True,
                "note": GIFT_ACCESS_NOTE,
            },
            **dashboard,
        }

    @router.get("/api/rewards/avatar")
    async def avatar_profile(
        request: Request,
        student_id: str | None = Query(default=None, max_length=80),
    ):
        account, learner = await authenticated_learner_context(request, student_id)
        avatar = await asyncio.to_thread(
            get_reward_store().avatar_summary,
            account_id=account["id"],
            student_id=learner["id"],
        )
        return {
            "success": True,
            "avatar": avatar,
            "learner": _avatar_age_context(learner),
        }

    @router.put("/api/rewards/avatar")
    async def customise_avatar(request: Request, body: AvatarPreferenceRequest):
        account, learner = await authenticated_learner_context(
            request, body.student_id
        )
        try:
            avatar = await asyncio.to_thread(
                get_reward_store().update_avatar,
                account_id=account["id"],
                student_id=learner["id"],
                character=body.character,
                clothes=body.clothes,
                bottoms=body.bottoms,
                shoes=body.shoes,
                skin_tone=body.skin_tone,
                hair_colour=body.hair_colour,
                hair_length=body.hair_length,
                hair_style=body.hair_style,
                eye_shape=body.eye_shape,
                eye_colour=body.eye_colour,
                nose=body.nose,
                mouth=body.mouth,
                eyebrows=body.eyebrows,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "success": True,
            "avatar": avatar,
            "learner": _avatar_age_context(learner),
            "message": "Your character style is saved!",
        }

    @router.post("/api/rewards/redemptions")
    async def request_reward(request: Request, body: RewardRequest):
        account, learner = await authenticated_learner_context(
            request, body.student_id
        )
        eligible = await gift_points_eligible(account)
        try:
            redemption = await asyncio.to_thread(
                get_reward_store().request_redemption,
                account_id=account["id"],
                student_id=learner["id"],
                reward_code=body.reward_code,
                gift_points_eligible=eligible,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "success": True,
            "redemption": redemption,
            "message": (
                "Your request is waiting for a grown-up. "
                "Your XP stays forever, and no Gift Points have been used yet."
            ),
        }

    @router.post("/api/rewards/custom-request")
    async def request_custom_reward(request: Request, body: CustomRewardRequest):
        """孩子提交自定义礼物请求（输入礼物名称和点数）。

        支持家长登录和孩子登录两种会话。
        """
        account, learner = await authenticated_learner_context(
            request, body.student_id
        )
        try:
            redemption = await asyncio.to_thread(
                get_reward_store().request_custom_redemption,
                account_id=account["id"],
                student_id=learner["id"],
                reward_name=body.reward_name,
                reward_icon=body.reward_icon,
                xp_cost=body.xp_cost,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "success": True,
            "redemption": redemption,
            "message": (
                "Your gift request has been sent to a grown-up. "
                "Gift Points will be used only after approval."
            ),
        }

    @router.post("/api/rewards/redemptions/{redemption_id}/decision")
    async def decide_reward(
        redemption_id: str,
        request: Request,
        body: RewardDecisionRequest,
    ):
        account = await account_context(request)
        eligible = await gift_points_eligible(account)
        if body.decision == "approve" and not eligible:
            raise HTTPException(status_code=403, detail=PARENT_GIFT_PLAN_NOTE)
        await confirm_parent(account, body.parent_password.get_secret_value())
        if body.decision == "approve" and body.delivery_address is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A parent or guardian must enter the adult recipient's "
                    "UK delivery address."
                ),
            )
        try:
            result = await asyncio.to_thread(
                get_reward_store().decide_redemption,
                account_id=account["id"],
                redemption_id=redemption_id,
                decision=body.decision,
                delivery_address=(
                    body.delivery_address.model_dump()
                    if body.delivery_address is not None
                    else None
                ),
                gift_points_eligible=eligible,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (RuntimeError, TypeError) as exc:
            raise HTTPException(
                status_code=503,
                detail="Gift delivery is not ready. Please contact Homework Magic.",
            ) from exc
        return {"success": True, **result}

    @router.get("/api/rewards/options")
    async def reward_options(request: Request):
        account = await account_context(request)
        eligible = await gift_points_eligible(account)
        return {
            "success": True,
            "gift_points_name": "Gift Points",
            "gift_points_eligible": eligible,
            "gift_points_requires_active_subscription": False,
            "gift_subscription_note": PARENT_GIFT_PLAN_NOTE,
            "delivery_country": "GB",
            "requires_parent_delivery_address": True,
            "xp_never_deducted": True,
        }

    @router.get("/admin/reward-orders")
    async def admin_reward_orders_page(request: Request):
        admin_context(request)
        if not project_root:
            raise HTTPException(status_code=404, detail="Page not found")
        page = Path(project_root) / "static" / "admin-reward-orders.html"
        if not page.is_file():
            raise HTTPException(status_code=404, detail="Page not found")
        return FileResponse(
            str(page),
            headers={
                "Cache-Control": "no-store, private",
                "Pragma": "no-cache",
            },
        )

    @router.get("/api/admin/reward-orders")
    async def admin_reward_orders(
        request: Request,
        status: str | None = Query(default=None, max_length=20),
        limit: int = Query(default=100, ge=1, le=200),
    ):
        admin_context(request)
        try:
            orders = await asyncio.to_thread(
                get_reward_store().list_reward_orders,
                status=status,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"success": True, "orders": orders}

    @router.get("/api/admin/reward-orders/{redemption_id}")
    async def admin_reward_order(
        redemption_id: str,
        request: Request,
    ):
        admin_context(request)
        try:
            order = await asyncio.to_thread(
                get_reward_store().get_reward_order,
                redemption_id=redemption_id,
            )
        except (RuntimeError, TypeError) as exc:
            raise HTTPException(
                status_code=500,
                detail="The encrypted delivery address could not be opened.",
            ) from exc
        if order is None:
            raise HTTPException(status_code=404, detail="Gift order not found")
        return {"success": True, **order}

    @router.post("/api/admin/reward-orders/{redemption_id}/decision")
    async def admin_decide_reward_order(
        redemption_id: str,
        request: Request,
        body: AdminGiftOrderDecisionRequest,
    ):
        admin_context(request)
        try:
            result = await asyncio.to_thread(
                get_reward_store().decide_reward_order,
                redemption_id=redemption_id,
                decision=body.decision,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"success": True, **result}

    # 家长自定义奖励目录管理

    @router.get("/api/rewards/catalog")
    async def list_custom_catalog(request: Request):
        """家长查看为该家庭创建的自定义奖励列表。"""
        account = await account_context(request)
        items = await asyncio.to_thread(
            get_reward_store().list_catalog_items,
            account_id=account["id"],
            include_inactive=True,
        )
        return {"success": True, "items": items}

    @router.post("/api/rewards/catalog")
    async def create_custom_catalog_item(
        request: Request, body: CatalogItemRequest
    ):
        """家长创建自定义奖励（如书本、电影票、足球等）。"""
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        try:
            item = await asyncio.to_thread(
                get_reward_store().create_catalog_item,
                account_id=account["id"],
                name=body.name,
                icon=body.icon,
                xp_cost=body.xp_cost,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"success": True, "item": item}

    @router.put("/api/rewards/catalog/{item_id}")
    async def update_custom_catalog_item(
        item_id: str, request: Request, body: CatalogItemUpdateRequest
    ):
        """家长更新自定义奖励。"""
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        try:
            item = await asyncio.to_thread(
                get_reward_store().update_catalog_item,
                account_id=account["id"],
                item_id=item_id,
                name=body.name,
                icon=body.icon,
                xp_cost=body.xp_cost,
                is_active=body.is_active,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"success": True, "item": item}

    @router.delete("/api/rewards/catalog/{item_id}")
    async def delete_custom_catalog_item(
        item_id: str, request: Request, body: ParentPasswordRequest
    ):
        """家长删除自定义奖励。"""
        account = await account_context(request)
        await confirm_parent(account, body.parent_password.get_secret_value())
        deleted = await asyncio.to_thread(
            get_reward_store().delete_catalog_item,
            account_id=account["id"],
            item_id=item_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Reward not found")
        return {"success": True}

    @router.post("/api/rewards/redemptions/{redemption_id}/parent-decision")
    async def parent_decide_redemption(
        redemption_id: str,
        request: Request,
        body: ParentRedemptionDecisionRequest,
    ):
        """家长审批/拒绝孩子的奖励请求，可自定义扣除的 XP 数量。

        奖励为线下交接（如书本、电影票），无需配送地址。
        """
        account = await account_context(request)
        eligible = await gift_points_eligible(account)
        if body.decision == "approve" and not eligible:
            raise HTTPException(status_code=403, detail=PARENT_GIFT_PLAN_NOTE)
        await confirm_parent(account, body.parent_password.get_secret_value())
        try:
            result = await asyncio.to_thread(
                get_reward_store().decide_redemption_with_custom_xp,
                account_id=account["id"],
                redemption_id=redemption_id,
                decision=body.decision,
                xp_to_deduct=body.xp_to_deduct,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"success": True, **result}

    @router.get("/rewards/certificate/{certificate_code}")
    async def printable_certificate(
        certificate_code: str,
        request: Request,
        student_id: str = Query(min_length=1, max_length=80),
    ):
        account, learner = await authenticated_learner_context(request, student_id)
        certificate = await asyncio.to_thread(
            get_reward_store().get_certificate,
            account_id=account["id"],
            student_id=learner["id"],
            certificate_code=certificate_code,
        )
        if certificate is None:
            raise HTTPException(
                status_code=404,
                detail="This certificate has not been unlocked yet.",
            )
        unlocked = datetime.fromisoformat(certificate["unlocked_at"])
        date_label = f"{unlocked.day} {unlocked.strftime('%B %Y')}"
        learner_name = html.escape(str(learner["name"]))
        title = html.escape(str(certificate["title"]))
        message = html.escape(str(certificate["message"]))
        icon = html.escape(str(certificate["icon"]))
        document = f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>{title} Certificate | Homework Magic</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      padding: 24px; color: #28304d; font-family: Georgia, serif;
      background: #f4f0ff;
    }}
    .certificate {{
      width: min(100%, 980px); min-height: 650px; padding: 62px;
      border: 14px solid #7357c8; outline: 4px solid #f7bf3c;
      outline-offset: -28px; background: #fffdf8; text-align: center;
      box-shadow: 0 18px 50px #35236b26;
    }}
    .brand {{ font: 700 20px system-ui, sans-serif; color: #6245bc; }}
    .icon {{ font-size: 72px; margin: 24px 0 8px; }}
    h1 {{ margin: 10px 0; color: #4c359b; font-size: clamp(38px, 7vw, 70px); }}
    .awarded {{ margin-top: 36px; font: 600 20px system-ui, sans-serif; }}
    .learner {{ margin: 14px auto; font-size: clamp(34px, 6vw, 62px); color: #19245c; }}
    .message {{
      max-width: 680px; margin: 18px auto 40px;
      font-size: 23px; line-height: 1.5;
    }}
    .date {{ font: 600 18px system-ui, sans-serif; }}
    .print {{
      position: fixed; right: 18px; bottom: 18px; border: 0; border-radius: 999px;
      padding: 13px 22px; color: white; background: #5a3db1; font: 700 16px system-ui;
      cursor: pointer;
    }}
    @media print {{
      @page {{ size: landscape; margin: 0; }}
      body {{ padding: 0; background: white; }}
      .certificate {{ width: 100vw; min-height: 100vh; box-shadow: none; }}
      .print {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main class="certificate">
    <div class="brand">✨ Homework Magic</div>
    <div class="icon" aria-hidden="true">{icon}</div>
    <p class="awarded">This certificate is proudly awarded to</p>
    <h1 class="learner">{learner_name}</h1>
    <h2>{title}</h2>
    <p class="message">{message}.</p>
    <p class="date">Unlocked on {date_label}</p>
  </main>
  <button class="print" type="button" onclick="window.print()">
    Print certificate
  </button>
</body>
</html>"""
        return HTMLResponse(
            document,
            headers={
                "Cache-Control": "no-store, private",
                "Pragma": "no-cache",
                "X-Robots-Tag": "noindex, nofollow",
            },
        )

    return router
