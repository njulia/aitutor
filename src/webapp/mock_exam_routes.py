"""FastAPI routes for locally generated and scored 11+ mock exams."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
import hashlib
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

from .runtime import is_30_day_study_plan_enabled, run_blocking


logger = logging.getLogger(__name__)


_EXPLANATION_SECTION_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?"
    r"(How to solve it|Why it works|Helpful tip)\s*:?\s*$"
)

# Each app event loop shares one in-flight task per reviewed question.  Waiting
# requests await this task without taking an AI-worker permit, which prevents a
# popular question from filling the AI pool with threads blocked on a lock.
_mock_explanation_tasks: Dict[tuple[int, str], asyncio.Task[tuple[str, bool]]] = {}


def _split_explanation_sections(explanation: Any) -> Dict[str, str]:
    """Read the three child-facing explanation sections from Markdown text."""
    text = str(explanation or "").strip()
    parts = {"solve": "", "why": "", "tip": ""}
    if not text:
        return parts

    headings = list(_EXPLANATION_SECTION_RE.finditer(text))
    if not headings:
        parts["solve"] = text
        return parts

    preamble = text[:headings[0].start()].strip()
    if preamble:
        parts["solve"] = preamble
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        content = text[heading.end():end].strip()
        key = {
            "how to solve it": "solve",
            "why it works": "why",
            "helpful tip": "tip",
        }[heading.group(1).casefold()]
        if content:
            parts[key] = (parts[key] + "\n\n" + content).strip()
    return parts


def _render_explanation_sections(parts: Dict[str, str]) -> str:
    """Return the same predictable layout used by 11+ Topic Mastery."""
    return "\n\n".join((
        "## How to solve it\n" + str(parts.get("solve") or "").strip(),
        "## Why it works\n" + str(parts.get("why") or "").strip(),
        "## Helpful tip\n" + str(parts.get("tip") or "").strip(),
    )).strip()


def _trusted_mock_explanation(question: Dict[str, Any]) -> str:
    """Make a useful, always-available explanation from verified mock content."""
    subject = str(question.get("subject") or "11+").strip()
    topic = str(question.get("topic") or "this skill").strip()
    working = str(question.get("explanation") or "").strip()
    if not working:
        working = (
            "Read the question slowly, complete one small step at a time, and "
            "then compare your result with every option."
        )

    subject_key = subject.casefold()
    if "verbal" in subject_key:
        tip = "Look for the relationship or clue first, then test it against every option."
    elif "non-verbal" in subject_key or "non verbal" in subject_key:
        tip = "Check one feature at a time, such as shape, direction, shading or number."
    elif "english" in subject_key:
        tip = "Underline the word or phrase that gives the strongest clue before choosing."
    else:
        tip = "Write down each small calculation, then do a quick check before choosing."

    return _render_explanation_sections({
        "solve": working,
        "why": (
            f"The steps use the {topic} rule in the right order, so each part of "
            "the question is checked before you choose an option."
        ),
        "tip": tip,
    })


def _normalise_mock_explanation(explanation: Any, fallback: str) -> str:
    """Keep saved and generated text in the Topic Mastery explanation shape."""
    generated = _split_explanation_sections(explanation)
    trusted = _split_explanation_sections(fallback)
    return _render_explanation_sections({
        "solve": generated["solve"] or trusted["solve"],
        "why": generated["why"] or trusted["why"],
        "tip": generated["tip"] or trusted["tip"],
    })


def _mock_question_fingerprint(
    *,
    question_id: str,
    subject: Any,
    topic: Any,
    question_text: str,
    options: Any,
    correct_label: str,
    correct_text: str,
) -> str:
    """Create a cache key for this exact reviewed question and answer key."""
    option_lines = [
        f"{item.get('label', '')}. {item.get('text', '')}"
        for item in (options or [])
        if isinstance(item, dict)
    ]
    cache_material = "\n".join((
        "mock-explanation-v2",
        str(question_id or "").strip(),
        str(subject or "").strip(),
        str(topic or "").strip(),
        str(question_text or "").strip(),
        *option_lines,
        str(correct_label or "").strip(),
        str(correct_text or "").strip(),
    ))
    return hashlib.sha256(cache_material.encode("utf-8")).hexdigest()


def _create_or_load_mock_explanation(
    *,
    fingerprint: str,
    fallback: str,
    llm_client: Any,
    prompt: str,
    exam_id: str,
    question_id: str,
    question: Dict[str, Any],
) -> tuple[str, bool]:
    """Return a cached explanation or create and persist one in a worker thread.

    This deliberately treats cache and provider trouble as non-fatal.  Every
    mock question already has a reviewed short explanation, so a child should
    never be left without help just because the optional detailed-tutor call is
    busy or temporarily unavailable.
    """
    from src.progress_db import get_mock_exam_explanation, save_mock_exam_explanation
    from src.llm_client import build_messages
    from src.webapp.review_service import DETAIL_REVIEW_MODEL, _complete_review, _resolved_model

    try:
        cached = get_mock_exam_explanation(fingerprint)
    except Exception:
        logger.warning("Unable to load saved mock question explanation", exc_info=True)
        cached = None
    if cached and str(cached.get("explanation") or "").strip():
        saved = str(cached["explanation"])
        normalised = _normalise_mock_explanation(saved, fallback)
        if normalised != saved.strip():
            try:
                save_mock_exam_explanation(
                    fingerprint,
                    normalised,
                    model_used=cached.get("model_used"),
                )
            except Exception:
                logger.warning("Unable to update saved mock explanation layout", exc_info=True)
        return normalised, True

    generated = ""
    # Make a reviewed local fallback visible in admin diagnostics without
    # exposing it to the child-facing response.
    model_used = "trusted_mock_fallback"
    if llm_client is not None:
        try:
            # This runs within ``run_blocking`` below.  Calling provider SDKs
            # directly in the async route previously blocked the event loop,
            # making intermittent provider delays look like a failed answer.
            generated = _complete_review(
                llm_client,
                build_messages(prompt),
                model=DETAIL_REVIEW_MODEL,
                temperature=0.2,
                max_tokens=900,
                operation="mock_exam_question_detail_explanation",
            )
        except Exception:
            logger.warning("Unable to create mock question explanation; using reviewed fallback", exc_info=True)
        if str(generated or "").strip():
            try:
                model_used = _resolved_model(llm_client, DETAIL_REVIEW_MODEL)
            except Exception:
                # The explanation itself is still useful if optional model
                # metadata cannot be resolved.
                model_used = DETAIL_REVIEW_MODEL

    explanation = _normalise_mock_explanation(generated or fallback, fallback)
    try:
        save_mock_exam_explanation(
            fingerprint,
            explanation,
            exam_id=exam_id,
            question_id=question_id,
            subject=question.get("subject"),
            topic=question.get("topic"),
            model_used=model_used,
        )
    except Exception:
        # Saving is an optimisation.  A successful explanation must still
        # reach the child if a transient database write fails.
        logger.warning("Unable to save mock question explanation", exc_info=True)
    return explanation, False


async def _load_or_create_mock_explanation_once(
    *,
    fingerprint: str,
    fallback: str,
    llm_client: Any,
    prompt: str,
    exam_id: str,
    question_id: str,
    question: Dict[str, Any],
) -> tuple[str, bool]:
    """Coalesce same-question cache misses before entering the AI worker pool."""
    loop = asyncio.get_running_loop()
    task_key = (id(loop), fingerprint)
    task = _mock_explanation_tasks.get(task_key)

    if task is None:
        async def create() -> tuple[str, bool]:
            try:
                return await run_blocking(
                    _create_or_load_mock_explanation,
                    fingerprint=fingerprint,
                    fallback=fallback,
                    llm_client=llm_client,
                    prompt=prompt,
                    exam_id=exam_id,
                    question_id=question_id,
                    question=question,
                    # A concise, structured answer is faster and easier for a
                    # child to read than the previous 1,800-token free-form call.
                    timeout=40,
                )
            except Exception:
                # A provider/queue failure should never leave a child with a
                # red error panel after completing a mock.
                logger.warning(
                    "Unable to create mock question explanation; using reviewed fallback",
                    exc_info=True,
                )
                return fallback, False

        task = asyncio.create_task(create())
        _mock_explanation_tasks[task_key] = task

        def discard_when_finished(completed: asyncio.Task[tuple[str, bool]]) -> None:
            if _mock_explanation_tasks.get(task_key) is completed:
                _mock_explanation_tasks.pop(task_key, None)

        task.add_done_callback(discard_when_finished)

    # Shield the shared work from one browser navigation/cancelled request.
    return await asyncio.shield(task)


class MockExamSubmission(BaseModel):
    attempt_token: str = Field(min_length=20, max_length=4096)
    answers: Dict[str, str] = Field(default_factory=dict)


def build_mock_exam_router(
    *,
    resolve_identity: Callable[[Request], tuple[str, Optional[str], Optional[str]]],
    has_subscription: Callable[..., bool],
    set_anon_cookie: Callable[[JSONResponse, Optional[str], Request], None],
    get_llm_client: Callable[[], Any] = lambda: None,
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
        """Return the latest 30-day plan when the feature is enabled and entitled."""
        if not is_30_day_study_plan_enabled():
            raise HTTPException(status_code=404, detail="The 30-day study plan is currently disabled.")
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

    @router.post("/{exam_id}/questions/{question_id}/explanation")
    async def question_explanation(exam_id: str, question_id: str, request: Request):
        """Return one reusable, question-specific mock explanation."""
        exam = EXAMS.get(str(exam_id or "").strip())
        if exam is None or question_id not in set(exam.get("question_ids") or []):
            raise HTTPException(status_code=404, detail="This mock question is not available.")
        _identity, _username, new_anon_id, has_access = await access_context(request)
        if exam["id"] != FREE_MOCK_EXAM_ID and not has_access:
            response = private_json({
                "success": False,
                "locked": True,
                "required_plan": MOCK_EXAM_PLAN,
                "required_plan_name": MOCK_EXAM_PLAN_NAME,
                "pricing_url": "/pricing",
            }, status_code=402)
            set_anon_cookie(response, new_anon_id, request)
            return response

        from src.elevenplus_mock_exams import _QUESTION_BY_ID
        from src.progress_db import get_mock_exam_explanation, save_mock_exam_explanation
        question = _QUESTION_BY_ID.get(question_id)
        if not question:
            raise HTTPException(status_code=404, detail="This question is not available.")
        question_prompt = str(question.get("prompt") or question.get("question") or "").strip()
        question_context = str(question.get("context") or "").strip()
        question_text = "\n\n".join(
            part for part in (question_context, question_prompt) if part
        )
        options = question.get("options") or []
        correct_label = str(question.get("answer") or "").strip()
        correct_text = next(
            (str(item.get("text") or "").strip() for item in options if item.get("label") == correct_label),
            "",
        )
        fingerprint = _mock_question_fingerprint(
            question_id=question_id,
            subject=question.get("subject"),
            topic=question.get("topic"),
            question_text=question_text,
            options=options,
            correct_label=correct_label,
            correct_text=correct_text,
        )
        fallback = _trusted_mock_explanation(question)

        # Cache lookup stays deliberately fast and outside the AI queue.  If a
        # database replica is briefly unavailable, the route can still return
        # the reviewed fallback rather than showing an error to a child.
        try:
            cached = await run_blocking(
                get_mock_exam_explanation,
                fingerprint,
                timeout=5,
                limit_concurrency=False,
            )
        except Exception:
            logger.warning("Unable to load saved mock question explanation", exc_info=True)
            cached = None
        if cached and str(cached.get("explanation") or "").strip():
            saved = str(cached["explanation"])
            explanation = _normalise_mock_explanation(saved, fallback)
            if explanation != saved.strip():
                try:
                    await run_blocking(
                        save_mock_exam_explanation,
                        fingerprint,
                        explanation,
                        model_used=cached.get("model_used"),
                        timeout=5,
                        limit_concurrency=False,
                    )
                except Exception:
                    logger.warning("Unable to update saved mock explanation layout", exc_info=True)
            response = private_json({
                "success": True,
                "explanation": explanation,
                "question_id": question_id,
                "from_saved": True,
            })
            set_anon_cookie(response, new_anon_id, request)
            return response

        try:
            llm_client = get_llm_client()
        except Exception:
            logger.warning("Unable to initialise mock question explanation service", exc_info=True)
            llm_client = None
        prompt = f"""You are a friendly UK 11+ tutor for a child aged 9-11.
Explain this one multiple-choice question step by step so the child can learn the method.
Use simple, clear language.
Do not mention the child's answer.
Do not state the correct option letter or give a standalone final answer.
You may use the trusted answer information below to make the reasoning accurate, but do not reveal it directly.
Use exactly this Markdown structure:
## How to solve it
## Why it works
## Helpful tip
Keep each section short and useful. End the Helpful tip with a short 'Remember' tip.

Subject: {question.get('subject','11+')}
Topic: {question.get('topic','General')}
Question:
{question_text}

Options:
{chr(10).join(f"{item.get('label','')}. {item.get('text','')}" for item in options)}

Trusted answer information (do not reveal directly):
Correct option: {correct_label}
Correct option text: {correct_text}
"""
        try:
            explanation, loaded_while_waiting = await _load_or_create_mock_explanation_once(
                fingerprint=fingerprint,
                fallback=fallback,
                llm_client=llm_client,
                prompt=prompt,
                exam_id=exam_id,
                question_id=question_id,
                question=question,
            )
        except Exception:
            # A queue timeout or provider failure should never leave a child
            # with a red error panel after completing a mock.  The fallback is
            # derived from reviewed local question content, not a guess.
            logger.warning("Unable to create mock question explanation; using reviewed fallback", exc_info=True)
            explanation = fallback
            loaded_while_waiting = False
        response = private_json({
            "success": True,
            "explanation": explanation,
            "question_id": question_id,
            "from_saved": bool(loaded_while_waiting),
        })
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
        if is_30_day_study_plan_enabled() and exam and exam["id"] != FREE_MOCK_EXAM_ID:
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
