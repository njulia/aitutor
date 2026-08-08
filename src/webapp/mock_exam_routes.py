"""FastAPI routes for locally generated and scored 11+ mock exams."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
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
        # 测试用户可以直接访问 11+ mock exams，无需订阅检查
        if username:
            from src.progress_db import is_user_test
            if is_user_test(username):
                return identity, username, new_anon_id, True
        # ``identity`` is a real learner ID for both parent-selected and kid
        # sessions. The subscription helper resolves a kid's family plan from
        # that ID, so children do not need access to a parent's email/session.
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
    async def submit(exam_id: str, body: MockExamSubmission, request: Request):
        identity, _username, new_anon_id = resolve_identity(request)
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
        response = private_json(result)
        set_anon_cookie(response, new_anon_id, request)
        return response

    return router
