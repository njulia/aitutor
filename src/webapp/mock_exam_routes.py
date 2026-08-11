"""FastAPI routes for locally generated and scored 11+ mock exams."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.elevenplus_mock_exams import (
    EXAMS,
    FREE_MOCK_EXAM_ID,
    MOCK_EXAM_PLAN,
    MOCK_EXAM_PLAN_NAME,
    ExpiredAttempt,
    InvalidAttempt,
    MockExamError,
    MockExamNotFound,
    mock_exam_catalogue,
    score_mock_exam,
    start_mock_exam,
)

from .runtime import run_blocking


logger = logging.getLogger(__name__)


class MockExamSubmission(BaseModel):
    attempt_token: str = Field(min_length=20, max_length=4096)
    answers: Dict[str, str] = Field(default_factory=dict)


def build_mock_exam_router(
    *,
    resolve_identity: Callable[[Request], tuple[str, Optional[str], Optional[str]]],
    has_subscription: Callable[..., bool],
    set_anon_cookie: Callable[[JSONResponse, Optional[str], Request], None],
) -> APIRouter:
    """Build the mock router without coupling it to the main application module."""
    router = APIRouter(prefix="/api/elevenplus/mock-exams", tags=["11+ mock exams"])

    async def access_context(request: Request) -> tuple[str, Optional[str], Optional[str], bool]:
        identity, username, new_anon_id = resolve_identity(request)
        # ``identity`` is a real learner ID for both parent-selected and kid
        # sessions. The subscription helper resolves a kid's family plan from
        # that ID, so children do not need access to a parent's email/session.
        # It also owns the operator-controlled test-user bypass, including kid
        # sessions where no parent email is exposed to this route.
        try:
            has_access = await run_blocking(
                has_subscription,
                request,
                identity,
                username,
                MOCK_EXAM_PLAN,
                True,
                timeout=8,
                limit_concurrency=False,
            )
        except Exception:
            # Paid mocks fail closed, but the public diagnostic must remain in
            # the catalogue even if an entitlement lookup is unavailable.
            logger.exception(
                "Unable to check 11+ mock access (identity=%s)",
                str(identity)[:20],
            )
            has_access = False
        return identity, username, new_anon_id, bool(has_access)

    def private_json(content: Dict[str, Any], status_code: int = 200) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=content,
            headers={"Cache-Control": "no-store, private"},
        )

    @router.get("")
    async def catalogue(request: Request):
        identity, _username, new_anon_id, has_access = await access_context(request)
        del identity
        response = private_json(mock_exam_catalogue(has_mock_access=has_access))
        set_anon_cookie(response, new_anon_id, request)
        return response

    @router.get("/study-plan")
    async def study_plan(request: Request):
        """Return the latest 30-day plan when the family has 11+ Premium."""
        identity, _username, new_anon_id, has_access = await access_context(request)
        if not has_access:
            response = private_json({
                "success": False,
                "locked": True,
                "required_plan": MOCK_EXAM_PLAN,
                "required_plan_name": MOCK_EXAM_PLAN_NAME,
                "pricing_url": "/pricing",
            }, status_code=402)
            set_anon_cookie(response, new_anon_id, request)
            return response
        from src.progress_db import get_mock_study_plan
        plan = await run_blocking(
            get_mock_study_plan, identity, timeout=8, limit_concurrency=False
        )
        plan_status = None
        if isinstance(plan, dict):
            plan_status = plan.get("status")
        response = private_json({
            "success": True,
            "locked": False,
            "ready": bool(plan) and plan_status not in {"preparing", "processing"},
            "status": plan_status or ("ready" if plan else "none"),
            "has_mock_exam": bool(plan),
            "plan": plan if plan_status not in {"preparing", "processing"} else None,
        })
        set_anon_cookie(response, new_anon_id, request)
        return response

    @router.post("/{exam_id}/start")
    async def start(exam_id: str, request: Request):
        exam = EXAMS.get(str(exam_id or "").strip())
        if exam is None:
            raise HTTPException(status_code=404, detail="This mock exam is not available.")
        is_free_mock = exam["id"] == FREE_MOCK_EXAM_ID

        identity: str
        username: Optional[str]
        new_anon_id: Optional[str]
        has_access: bool

        # 免费 diagnostic 考试：不调用 resolve_identity（含数据库查询），直接使用 cookie 中的匿名 ID，
        # 确保在任何情况下（包括数据库不可用时）任何用户都能访问免费诊断
        if is_free_mock:
            anonymous_id = request.cookies.get("anon_session_id")
            new_anon_id: Optional[str] = None
            if not anonymous_id:
                import uuid
                anonymous_id = f"anon_{uuid.uuid4().hex}"
                new_anon_id = anonymous_id
            identity = anonymous_id
            username = None
            has_access = True
        else:
            identity, username, new_anon_id, has_access = await access_context(request)

        if not is_free_mock and not has_access:
            response = private_json(
                {
                    "success": False,
                    "error": (
                        "A parent or guardian needs to sign in. "
                        if not username and str(identity).startswith("anon_")
                        else ""
                    )
                    + f"This mock requires {MOCK_EXAM_PLAN_NAME}.",
                    "required_plan": MOCK_EXAM_PLAN,
                    "required_plan_name": MOCK_EXAM_PLAN_NAME,
                    "pricing_url": "/pricing",
                },
                status_code=(
                    401
                    if not username and str(identity).startswith("anon_")
                    else 402
                ),
            )
            set_anon_cookie(response, new_anon_id, request)
            return response
        try:
            result = start_mock_exam(exam_id, identity)
        except MockExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(
                "Unable to start 11+ mock exam (exam_id=%s identity=%s): %s",
                exam_id,
                str(identity)[:20],
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail="We could not start this mock just now. Please try again.",
            ) from exc
        response = private_json(result)
        set_anon_cookie(response, new_anon_id, request)
        return response

    @router.post("/{exam_id}/submit")
    async def submit(
        exam_id: str,
        body: MockExamSubmission,
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        identity, _username, new_anon_id = resolve_identity(request)
        # 免费 diagnostic 考试提交时，也使用 cookie 中的匿名 ID，与 start 时保持一致
        exam = EXAMS.get(str(exam_id or "").strip())
        if exam and exam["id"] == FREE_MOCK_EXAM_ID:
            anonymous_id = request.cookies.get("anon_session_id")
            if anonymous_id:
                identity = anonymous_id
        try:
            result = score_mock_exam(
                exam_id,
                body.attempt_token,
                identity,
                body.answers,
            )
        except MockExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ExpiredAttempt as exc:
            raise HTTPException(status_code=410, detail=str(exc)) from exc
        except InvalidAttempt as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except MockExamError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Unable to score 11+ mock exam")
            raise HTTPException(
                status_code=500,
                detail="We could not mark this mock just now. Please try again.",
            ) from exc

        # Paid mocks automatically start an adaptive 30-day plan build. The
        # generation is deliberately a background task so marking the exam stays
        # fast even when an LLM fallback is needed. The free diagnostic remains
        # a diagnostic only and does not create a premium study plan.
        if exam and exam["id"] != FREE_MOCK_EXAM_ID:
            try:
                from src.progress_db import get_student_detail, save_mock_study_plan
                from src.elevenplus_study_plan import generate_mock_study_plan
                student = get_student_detail(identity) or {}
                # Persist the preparing state so the app tab remains available
                # after the child leaves the mock-results page.
                save_mock_study_plan(str(identity), {
                    "status": "preparing",
                    "days": 30,
                    "minutes_per_day": 30,
                    "access": "11+ Premium",
                })
                year_group = max(1, min(int(student.get("year_group") or 5), 6))
                background_tasks.add_task(
                    generate_mock_study_plan,
                    student_id=str(identity),
                    year_group=year_group,
                    exam_result=result,
                )
                result["study_plan"] = {
                    "status": "preparing",
                    "access": "11+ Premium",
                    "days": 30,
                    "minutes_per_day": 30,
                }
            except Exception:
                logger.exception("Could not queue adaptive 11+ study plan")
                result["study_plan"] = {
                    "status": "unavailable",
                    "access": "11+ Premium",
                    "days": 30,
                    "minutes_per_day": 30,
                }
        response = private_json(result)
        set_anon_cookie(response, new_anon_id, request)
        return response

    return router
