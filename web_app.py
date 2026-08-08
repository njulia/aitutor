import os
import sys

# 加载 .env 环境变量（必须在其他 import 之前）
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import asyncio
import logging
import copy
import re  # Ensure re is imported for regex operations
import html
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse
from pydantic import BaseModel, Field

from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image
from src.progress_db import is_user_test, get_user_by_username

from src.webapp.runtime import (
    configure_cors, install_hardening, owner_key, run_blocking,
    production_configuration_issues, validate_production_configuration,
)
from src.webapp.session_store import TutorSessionStore
from src.webapp.upload_utils import normalised_extension, stream_upload_to_temp
from src.webapp.message_routes import create_message_router
from src.webapp.account_routes import build_account_router
from src.webapp.account_store import PREMIUM_PLAN_NAMES, HOMEWORK_PREMIUM_PLAN, ELEVENPLUS_PREMIUM_PLAN
from src.webapp.memory_routes import build_memory_router
from src.webapp.mock_exam_routes import build_mock_exam_router
from src.webapp.password_reset_routes import create_password_reset_router
from src.webapp.billing import build_billing_router
from src.webapp.reward_routes import build_reward_router
from src.webapp.parent_dashboard_routes import build_parent_dashboard_router
from src.webapp.email_service import send_registration_confirmation_email
from src.webapp.privacy_metrics import (
    marketing_summary,
    record_marketing_event,
    record_voice_event,
    voice_summary,
)
from src.webapp.question_utils import (
    _split_homework_into_questions as split_public_homework,
    parse_public_questions,
    public_homework_content,
)
from src.webapp.review_service import (
    DETAIL_REVIEW_MODEL,
    review_homework as service_review_homework,
    explain_deep as service_explain_deep,
    improve_practice as service_improve_practice,
)
from src.webapp.upload_utils import decode_base64_image_to_temp
from src.webapp.child_safety import detect_safeguarding_concern
from src.webapp.prompt_budget import compact_text, minimise_personal_data
from src.models import (
    ELEVEN_PLUS_SUBJECTS,
    ELEVEN_PLUS_TOPIC_MASTERY_SUBJECTS,
    ELEVEN_PLUS_YEAR_ROUND_SUBJECTS,
    canonical_primary_subject,
    extract_primary_subjects,
)


project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Stripe configuration（开发模式下可跳过）
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_dev_mode = os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")

if not _dev_mode and STRIPE_SECRET_KEY:
    import stripe

    stripe.api_key = STRIPE_SECRET_KEY
elif not _dev_mode:
    logger_init = logging.getLogger(__name__)
    logger_init.warning("STRIPE_SECRET_KEY not set and DEV_MODE is off. Subscription creation will fail.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(project_root, "uploads")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "heic", "gif"}
ALLOWED_TEXT_EXTENSIONS = {"txt", "md", "csv"}
ALLOWED_PDF_EXTENSION = {"pdf"}
MAX_UPLOAD_BYTES = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

llm = None
initialized = False
tutor_session_store = TutorSessionStore()

# HOMEWORK_PREMIUM_PLAN = "homework_monthly"
# ELEVENPLUS_PREMIUM_PLAN = "elevenplus_monthly"
# FAMILY_MONTHLY_PLAN = "family_monthly"
# FAMILY_11PLUS_MONTHLY_PLAN = "family_11plus_monthly"

# PREMIUM_PLAN_NAMES = {
#     HOMEWORK_PREMIUM_PLAN: "Homework Premium",
#     ELEVENPLUS_PREMIUM_PLAN: "11+ Premium",
#     FAMILY_MONTHLY_PLAN: "Family (Years 1-6)",
#     FAMILY_11PLUS_MONTHLY_PLAN: "Family (Years 1-6 + 11+)",
# }

OUT_OF_SCOPE_HOMEWORK_MESSAGE = (
    "Sorry, I can only make homework for UK primary school subjects and 11+ practice. "
    "I cannot generate that content because of our safety, privacy and learning policy."
)


def _is_eleven_plus_year_round(profile: Optional[dict] = None, subject: str = "") -> bool:
    profile = profile or {}
    try:
        if 1 <= int(profile.get("plan_week") or 0) <= 52:
            return True
    except (TypeError, ValueError):
        pass
    return str(subject or "").strip().lower().endswith("-1year")


def _required_premium_plan(
    *,
    is_eleven_plus: bool = False,
    profile: Optional[dict] = None,
    subject: str = "",
) -> str:
    if is_eleven_plus or _is_eleven_plus_year_round(profile, subject):
        return ELEVENPLUS_PREMIUM_PLAN
    return HOMEWORK_PREMIUM_PLAN


def _subscription_required_response(feature: str, plan: str, username: Optional[str], student_id: Optional[str] = None) -> JSONResponse:
    plan_name = PREMIUM_PLAN_NAMES.get(plan, "Premium")
    # 孩子登录会话（有真实 student_id 但无 username）：返回 402 而非 401，
    # 避免前端误判为未登录而跳转到 /login
    if username is None and not (student_id and not str(student_id).startswith("anon_")):
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": f"A parent or guardian needs to sign in. {feature} requires {plan_name}.",
                "required_plan": plan,
                "required_plan_name": plan_name,
            },
        )
    return JSONResponse(
        status_code=402,
        content={
            "success": False,
            "error": f"{feature} requires {plan_name}.",
            "required_plan": plan,
            "required_plan_name": plan_name,
        },
    )


def secure_filename(filename: str) -> str:
    """Sanitize uploaded filenames (werkzeug replacement)."""
    filename = re.sub(r"[^\w\s\-_\.]", "", filename)
    filename = filename.replace(" ", "_").lstrip(".")
    return filename or "unnamed_file"


def initialize() -> None:
    """Initialize LLM and related components."""
    global llm, initialized
    if initialized:
        return

    from src.llm_client import LLMClient

    llm = LLMClient()
    initialized = True
    logger.info("Web application initialized")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate configuration and perform small bounded maintenance tasks."""
    validate_production_configuration()
    initialize()
    # Initialise account, kid-session and reward/avatar tables before traffic.
    try:
        from src.webapp.account_store import init_account_db
        from src.webapp.kid_session_store import init_kid_session_db
        from src.webapp.reward_store import get_reward_store
        await asyncio.gather(
            asyncio.to_thread(init_account_db),
            asyncio.to_thread(init_kid_session_db),
            asyncio.to_thread(get_reward_store),
        )
    except Exception:
        logger.exception("Account database initialization failed")
    try:
        from src.auth_tokens import purge_expired as purge_auth_sessions
        from src.progress_db import purge_old_learning_records

        await asyncio.gather(
            asyncio.to_thread(purge_auth_sessions),
            asyncio.to_thread(tutor_session_store.purge_expired),
            asyncio.to_thread(purge_old_learning_records),
        )
    except Exception:
        logger.exception("Startup retention cleanup failed")
    yield


def _resolve_username(req: Request) -> Optional[str]:
    """Resolve the authenticated parent/admin email from the signed session token."""
    try:
        # A valid child session always wins over a stale parent cookie. This
        # prevents child-facing browsers from reaching parent-only endpoints.
        kid_token = req.cookies.get("kid_session") or req.headers.get("X-Kid-Session")
        if kid_token:
            from src.webapp.kid_session_store import resolve_kid_session

            if resolve_kid_session(kid_token):
                return None
        from src.auth_tokens import verify_token

        token = req.cookies.get("session") or req.headers.get("Authorization")
        if not token:
            return None
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        username = verify_token(token)
        if username and get_user_by_username(username):
            return str(username).strip().lower()
    except Exception:
        return None
    return None


def _cookie_should_be_secure(req: Request) -> bool:
    """Use Secure cookies on HTTPS, while allowing local HTTP development.

    COOKIE_SECURE can explicitly force the setting. Otherwise honour the
    reverse-proxy scheme and the request URL. This avoids creating an unusable
    Secure cookie when the app is tested at http://localhost.
    """
    configured = os.getenv("COOKIE_SECURE", "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False

    forwarded_proto = (req.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    return req.url.scheme.lower() == "https"


def _require_admin(req: Request) -> str:
    """Require a logged-in account included in ADMIN_EMAILS/ADMIN_EMAIL."""
    username = _resolve_username(req)
    if not username:
        raise HTTPException(status_code=401, detail="Administrator login is required.")

    configured = os.getenv("ADMIN_EMAILS") or os.getenv("ADMIN_EMAIL") or ""
    allowed = {item.strip().lower() for item in configured.split(",") if item.strip()}
    if allowed and username not in allowed:
        raise HTTPException(status_code=403, detail="This account is not an administrator.")
    if not allowed and not _dev_mode:
        raise HTTPException(
            status_code=403,
            detail="ADMIN_EMAILS is not configured for the administrator inbox.",
        )
    return username


def is_logged_in(req: Request) -> bool:
    """Check whether the request has a valid session token cookie or header mapped to an existing user."""
    try:
        from src.auth_tokens import verify_token # Moved to top-level import
        token = req.cookies.get("session")
        username = None
        if token:
            username = verify_token(token) # Verify token returns username (email)
            if username and get_user_by_username(username): # Check if user exists in DB
                return True
        # Support header-based token for API calls
        header_token = req.headers.get("Authorization")
        if header_token:
            maybe = verify_token(header_token)
            if maybe and get_user_by_username(maybe): # Check if user exists in DB
                return True
    except Exception:
        pass
    return False


def user_has_subscription(
    req: Optional[Request] = None,
    student_id: Optional[str] = None,
    username: Optional[str] = None,
    required_plan: Optional[str] = None,
    strict_plan: bool = False,
) -> bool:
    """Read access from the local account database synchronised by Stripe webhooks.

    No network call is made on the request path. This lowers latency and avoids
    granting or denying access because Stripe is temporarily unavailable.
    """
    if req and (student_id is None or username is None):
        resolved_student_id, resolved_username, _ = _get_user_or_anonymous_id(req)
        student_id = student_id or resolved_student_id
        username = username or resolved_username
    if not username and not student_id:
        return False
    # 孩子登录会话：通过学生 ID 查询家庭订阅
    if not username and student_id and not str(student_id).startswith("anon_"):
        try:
            from src.webapp.account_store import subscription_active_for_student
            required_plans = [required_plan] if required_plan else None
            return subscription_active_for_student(
                student_id,
                required_plans=required_plans,
                strict_plans=strict_plan,
            )
        except Exception:
            logger.exception("Kid session subscription lookup failed")
            return False
    if not username or (student_id and str(student_id).startswith("anon_")):
        return False
    try:
        if is_user_test(username) and not strict_plan:
            return True
        from src.webapp.account_store import account_has_active_subscription

        required_plans = [required_plan] if required_plan else None
        if account_has_active_subscription(
            username,
            required_plans=required_plans,
            strict_plans=strict_plan,
        ):
            return True
        # Backward-compatible local developer subscriptions only. Production
        # access must come from verified Stripe webhook state.
        if _dev_mode:
            from src.progress_db import get_local_subscriptions_by_email
            local_subscriptions = get_local_subscriptions_by_email(username)
            if strict_plan:
                required_name = str(PREMIUM_PLAN_NAMES.get(required_plan) or "").casefold()
                return any(
                    item.get("status") == "active"
                    and required_name
                    and required_name in str(item.get("product_name") or "").casefold()
                    for item in local_subscriptions
                )
            return any(item.get("status") == "active" for item in local_subscriptions)
        return False
    except Exception:
        logger.exception("Subscription lookup failed")
        return False


async def _account_has_reward_subscription(account_id: str) -> bool:
    """Fail closed for gifts without stopping a learner from earning XP."""
    from src.webapp.account_store import account_has_active_reward_subscription

    try:
        return bool(
            await run_blocking(
                account_has_active_reward_subscription,
                account_id,
                timeout=10,
                limit_concurrency=False,
            )
        )
    except Exception:
        logger.exception("Could not check reward gift subscription")
        return False


app = FastAPI(
    title="Homework Magic",
    description="AI Tutor for UK Primary Schools",
    version="2.0.0",
    lifespan=lifespan,
)

configure_cors(app)
install_hardening(app, require_admin=_require_admin)


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def process_uploaded_file(file_path: str):
    filename = os.path.basename(file_path)
    file_ext = os.path.splitext(filename)[1].lower().lstrip(".")

    try:
        content = ""
        is_image = False
        if file_ext in ALLOWED_IMAGE_EXTENSIONS:
            logger.info("[File Upload] Processing image: %s", filename)
            content = extract_text_from_image(file_path)
            is_image = True
        elif file_ext in ALLOWED_TEXT_EXTENSIONS:
            logger.info("[File Upload] Processing text file: %s", filename)
            content = read_text_file(file_path)
        elif file_ext in ALLOWED_PDF_EXTENSION:
            logger.info("[File Upload] Processing PDF: %s", filename)
            content = read_pdf_file(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        return content, is_image
    finally:
        # Failed OCR/PDF parsing must not leave child uploads on ephemeral disk.
        try:
            os.remove(file_path)
        except OSError:
            pass


def process_base64_image(data_url: str) -> str:
    path = decode_base64_image_to_temp(data_url, max_bytes=MAX_UPLOAD_BYTES)
    try:
        return extract_text_from_image(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def resolve_profile(
        raw_profile: dict,
        *,
        quick_select: bool = False,
        year: Optional[int] = None,
        student_id: Optional[str] = None,
) -> dict:
    """Build a student profile from quick-select or natural-language input."""
    if quick_select:
        year = year or 3
        profile = {
            "year_group": year,
            "age": 5 + (year - 1),
            "student_id": student_id or f"student_{year}",
        }
        return profile

    profile = dict(raw_profile or {})
    description = profile.get("description")

    if description and not profile.get("year_group"):
        from src.ui.shared import parse_profile_from_natural_language

        parsed = parse_profile_from_natural_language(description, llm)
        if parsed:
            profile = parsed
        else:
            profile.setdefault("year_group", 3)
            profile.setdefault("age", 7)
            profile.setdefault("student_id", "student_custom")

    if student_id:
        profile["student_id"] = student_id

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 3)}_default"

    return profile


def _bounded_year(value: Any, *, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def normalise_guided_homework_profile(raw_profile: dict, student_id: str) -> dict:
    """Build the small, non-identifying profile used by guided primary homework."""
    source = dict(raw_profile or {})
    year_group = _bounded_year(
        source.get("year_group"), minimum=1, maximum=6, default=3
    )
    subject = canonical_primary_subject(source.get("subject")) or "Maths"
    try:
        requested_minutes = int(source.get("session_minutes"))
    except (TypeError, ValueError):
        requested_minutes = 15
    session_minutes = requested_minutes if requested_minutes in {10, 15, 20} else 15
    difficulty = str(source.get("difficulty") or "").strip().casefold()
    if difficulty not in {"gentle", "just_right", "challenge"}:
        difficulty = "just_right"

    profile = {
        "setup_source": "guided_homework",
        "year_group": year_group,
        "age": year_group + 5,
        "subject": subject,
        "preferred_session_minutes": session_minutes,
        "question_count": {10: 5, 15: 8, 20: 10}[session_minutes],
        "difficulty": difficulty,
        "student_id": student_id,
    }
    notes = compact_text(
        minimise_personal_data(source.get("learning_notes")), 500
    )
    if notes:
        profile["learning_needs"] = notes
    return profile


def guided_homework_client_profile(profile: dict) -> dict:
    """Return only profile fields that are useful to the browser."""
    allowed = {
        "year_group",
        "age",
        "subject",
        "preferred_session_minutes",
        "question_count",
        "difficulty",
    }
    return {key: profile[key] for key in allowed if key in profile}


def normalise_guided_eleven_profile(raw_profile: dict, student_id: str) -> dict:
    """Build a bounded 11+ setup profile without school or learner identifiers."""
    source = dict(raw_profile or {})
    year_group = _bounded_year(
        source.get("year_group"), minimum=3, maximum=6, default=5
    )
    compact_subject = "".join(
        char for char in str(source.get("subject") or "").casefold()
        if char.isalnum()
    )
    subject = {
        "maths": "Maths",
        "mathematics": "Maths",
        "english": "English",
        "verbalreasoning": "Verbal Reasoning",
        "nonverbalreasoning": "Non-Verbal Reasoning",
    }.get(compact_subject, "Maths")
    confidence = str(source.get("confidence") or "").strip().casefold()
    if confidence not in {"confident", "sometimes_tricky", "needs_help"}:
        confidence = "sometimes_tricky"
    try:
        requested_count = int(source.get("question_count"))
    except (TypeError, ValueError):
        requested_count = 8
    question_count = requested_count if requested_count in {5, 8} else 8

    profile = {
        "setup_source": "guided_11plus",
        "year_group": year_group,
        "age": year_group + 5,
        "subject": subject,
        "confidence": confidence,
        "question_count": question_count,
        "student_id": student_id,
    }
    exam_format = str(source.get("exam_format") or "").strip()
    if exam_format in {"GL Assessment", "CEM", "ISEB", "Not sure"}:
        profile["exam_format"] = exam_format
    exam_date = str(source.get("exam_date") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", exam_date):
        try:
            profile["exam_month"] = datetime.strptime(
                exam_date, "%Y-%m-%d"
            ).strftime("%B %Y")
        except ValueError:
            pass
    notes = compact_text(
        minimise_personal_data(source.get("learning_notes")), 500
    )
    if notes:
        profile["learning_needs"] = notes
    return profile


def guided_eleven_client_profile(profile: dict) -> dict:
    """Return the answer-free, non-identifying 11+ setup state."""
    allowed = {
        "year_group",
        "age",
        "subject",
        "confidence",
        "question_count",
        "exam_format",
        "exam_month",
    }
    return {key: profile[key] for key in allowed if key in profile}


def _format_public_questions(questions: List[Dict[str, Any]]) -> str:
    lines = ["QUESTIONS"]
    for index, item in enumerate(questions, start=1):
        number = int(item.get("number") or index)
        lines.append(f"{number}. {str(item.get('question') or '').strip()}")
        for option_index, option in enumerate(item.get("options") or []):
            if isinstance(option, dict):
                label = str(
                    option.get("label") or chr(65 + option_index)
                ).strip().upper()
                text = str(option.get("text") or "").strip()
            else:
                label = chr(65 + option_index)
                text = str(option or "").strip()
            if text:
                lines.append(f"{label}) {text}")
        lines.append("")
    return "\n".join(lines).strip()


def limit_homework_question_count(
    homework_results: List[Dict[str, Any]], question_count: int
) -> List[Dict[str, Any]]:
    """Return a copy containing at most the requested learner-safe questions."""
    limit = max(1, min(int(question_count or 1), 20))
    limited = copy.deepcopy(list(homework_results or []))
    for result in limited:
        questions = list(result.get("questions") or [])[:limit]
        for index, question in enumerate(questions, start=1):
            question["number"] = index
        result["questions"] = questions
        result["content"] = _format_public_questions(questions)
    return limited


def _get_user_or_anonymous_id(req: Request) -> tuple[str, Optional[str], Optional[str]]:
    """
    Determines the student_id and username for the current request.
    Returns (student_id, username_if_logged_in, new_anonymous_session_id_to_set_in_cookie).
    new_anonymous_session_id_to_set_in_cookie will be None if no new cookie is needed.
    """
    from src.auth_tokens import verify_token  # Moved to top-level import
    # 1. Check for kid session (family code + kid code login)
    kid_token = req.headers.get("X-Kid-Session") or req.cookies.get("kid_session")
    if kid_token:
        from src.webapp.kid_session_store import resolve_kid_session
        session = resolve_kid_session(kid_token)
        if session:
            # 孩子登录会话：返回学生 ID，无家长邮箱
            return str(session["student_id"]), None, None

    # 2. Check for logged-in parent user
    token = req.cookies.get("session") or req.headers.get("Authorization")
    if token:
        username = verify_token(token)
        if username and get_user_by_username(username):
            # The login belongs to a parent/guardian account. Resolve the
            # account's default learner instead of using the email as a learner ID.
            from src.webapp.account_store import ensure_account, ensure_default_student

            account = ensure_account(username)
            learner = ensure_default_student(account["id"])
            return str(learner["id"]), str(username).strip().lower(), None

    # 3. Check for anonymous session ID cookie
    anonymous_session_id = req.cookies.get("anon_session_id")
    if anonymous_session_id:
        return anonymous_session_id, None, None # No username for anonymous

    # 4. Generate a new anonymous session ID
    new_anon_session_id = f"anon_{uuid.uuid4().hex}" # Prefix to distinguish from real student_ids
    return new_anon_session_id, None, new_anon_session_id


async def _resolve_request_identity(
    req: Request,
) -> tuple[str, Optional[str], Optional[str]]:
    """Resolve account/learner data without blocking the FastAPI event loop."""
    # Import the runtime helper here so broad route-level test patches do not
    # accidentally replace identity resolution with an unrelated fake result.
    from src.webapp import runtime as web_runtime

    return await web_runtime.run_blocking(
        _get_user_or_anonymous_id,
        req,
        timeout=10,
        limit_concurrency=False,
    )


# Parent/guardian support messages and the protected administrator inbox.
app.include_router(create_message_router(
    resolve_identity=_get_user_or_anonymous_id,
    require_admin=_require_admin,
    project_root=project_root,
))

app.include_router(build_account_router(
    resolve_username=_resolve_username,
    require_admin=_require_admin,
    session_store=tutor_session_store,
))
app.include_router(build_memory_router(_resolve_username))
app.include_router(create_password_reset_router(project_root=project_root, dev_mode=_dev_mode))
app.include_router(build_billing_router(_resolve_username))
app.include_router(
    build_reward_router(
        _resolve_username,
        require_admin=_require_admin,
        project_root=project_root,
    )
)
app.include_router(build_parent_dashboard_router(_resolve_username))


def generate_homework_with_profile(profile: dict, subjects: list, is_eleven_plus: bool = False):
    """为多个科目生成作业（并行执行以降低延迟）"""
    from src.homework_generator import generate_homework_parallel

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 3)}_default"

    is_year_round = bool(is_eleven_plus) and (
        _is_eleven_plus_year_round(profile)
        or any(_is_eleven_plus_year_round(subject=subject) for subject in subjects or [])
    )
    selected_llm = llm
    if is_year_round and hasattr(llm, "with_model"):
        selected_llm = llm.with_model(DETAIL_REVIEW_MODEL)
    return generate_homework_parallel(
        profile,
        subjects,
        selected_llm,
        is_eleven_plus=is_eleven_plus,
    )


# Use the maintained, token-budgeted review service.  These wrappers keep the
# public module API stable for tests and existing integrations.
def review_homework(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile=None,
    *,
    quick_review: bool = False,
    uploaded_work: bool = False,
    is_tutor_mode: bool = False,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
):
    return service_review_homework(
        homework_content,
        student_answers,
        subject,
        profile,
        quick_review=quick_review,
        uploaded_work=uploaded_work,
        is_tutor_mode=is_tutor_mode,
        homework_doc_id=homework_doc_id,
        is_eleven_plus=is_eleven_plus,
        question_index=question_index,
        llm_client=llm,
    )


def explain_deep(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile=None,
    review_feedback: str = "",
    *,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
):
    return service_explain_deep(
        homework_content,
        student_answers,
        subject,
        profile,
        review_feedback,
        homework_doc_id=homework_doc_id,
        is_eleven_plus=is_eleven_plus,
        question_index=question_index,
        llm_client=llm,
    )


def improve_practice(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile=None,
    review_feedback: str = "",
    *,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
):
    return service_improve_practice(
        homework_content,
        student_answers,
        subject,
        profile,
        review_feedback,
        homework_doc_id=homework_doc_id,
        is_eleven_plus=is_eleven_plus,
        question_index=question_index,
        llm_client=llm,
    )


# Keep the old helper name while using the parser that preserves MCQ options,
# reading passages and answer-free learner content.
_split_homework_into_questions = split_public_homework

def _static_page(
    *parts: str,
    cache_control: str = "public, max-age=300, stale-while-revalidate=3600",
) -> FileResponse:
    path = os.path.join(project_root, *parts)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(path, headers={"Cache-Control": cache_control})


def _marketing_source(request: Request) -> str:
    """Return one coarse allow-listed source without retaining a URL or ID."""
    raw_source = str(request.query_params.get("utm_source") or "").strip().lower()
    aliases = {
        "whatsapp": "whatsapp",
        "school_whatsapp": "whatsapp",
        "facebook": "facebook",
        "fb": "facebook",
        "google": "organic",
        "google_ads": "google_ads",
        "googleads": "google_ads",
        "email": "email",
        "community": "community",
        "referral": "referral",
    }
    if raw_source in aliases:
        return aliases[raw_source]
    if request.query_params.get("gclid"):
        return "google_ads"
    referrer = request.headers.get("referer", "")
    if not referrer:
        return "direct"
    try:
        host = (urlparse(referrer).hostname or "").lower()
    except ValueError:
        return "unknown"
    if not host:
        return "unknown"
    if host.endswith(("google.com", "google.co.uk", "bing.com")):
        return "organic"
    if host.endswith(("facebook.com", "m.facebook.com")):
        return "facebook"
    if host.endswith(("homeworkmagic.co.uk", "www.homeworkmagic.co.uk")):
        return "direct"
    return "referral"


def _count_landing_visit(
    request: Request,
    background_tasks: BackgroundTasks,
    page: str,
) -> None:
    background_tasks.add_task(
        record_marketing_event,
        "landing_page_visit",
        source=_marketing_source(request),
        page=page,
    )


def _within_first_seven_days(created_at: Any) -> bool:
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(created_at, datetime):
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    age = datetime.now(UTC) - created_at.astimezone(UTC)
    return timedelta(0) <= age <= timedelta(days=7)


def _public_legal_page(
    filename: str,
    *,
    cache_control: str = "public, max-age=300",
) -> HTMLResponse:
    """Render public legal details from production-validated environment values."""
    path = os.path.join(project_root, "static", filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Page not found")
    with open(path, encoding="utf-8") as source:
        content = source.read()
    contact_email = (
        os.getenv("BUSINESS_CONTACT_EMAIL")
        or os.getenv("PRIVACY_CONTACT_EMAIL")
        or "contact@homeworkmagic.co.uk"
    )
    configured = {
        "DATA_CONTROLLER_NAME": os.getenv("DATA_CONTROLLER_NAME", "").strip(),
        "PRIVACY_CONTACT_EMAIL": os.getenv("PRIVACY_CONTACT_EMAIL", "").strip(),
        "PRIVACY_POSTAL_ADDRESS": os.getenv(
            "PRIVACY_POSTAL_ADDRESS", ""
        ).strip(),
    }
    missing = [name for name, value in configured.items() if not value]
    is_non_production = _dev_mode or os.getenv(
        "TESTING", ""
    ).strip().lower() in {"1", "true", "yes"}
    if missing and not is_non_production:
        logger.error(
            "Public legal page blocked because required operator settings are missing"
        )
        raise HTTPException(
            status_code=503,
            detail="The legal information page is temporarily unavailable.",
        )
    replacements = {
        "{{DATA_CONTROLLER_NAME}}": configured["DATA_CONTROLLER_NAME"]
        or "Homework Magic development operator",
        "{{BUSINESS_CONTACT_EMAIL}}": contact_email,
        "{{PRIVACY_CONTACT_EMAIL}}": configured["PRIVACY_CONTACT_EMAIL"]
        or contact_email,
        "{{PRIVACY_POSTAL_ADDRESS}}": configured["PRIVACY_POSTAL_ADDRESS"]
        or "Development environment (configure before public deployment)",
    }
    for marker, value in replacements.items():
        content = content.replace(marker, html.escape(str(value), quote=True))
    optional_lines = {
        "{{BUSINESS_SUPPORT_PHONE_LINE}}": (
            "<br>Telephone: <strong>"
            + html.escape(os.getenv("BUSINESS_SUPPORT_PHONE", ""), quote=True)
            + "</strong>"
            if os.getenv("BUSINESS_SUPPORT_PHONE", "").strip()
            else ""
        ),
        "{{BUSINESS_REGISTRATION_LINE}}": (
            "<br>Registration number: <strong>"
            + html.escape(
                os.getenv("BUSINESS_REGISTRATION_NUMBER", ""), quote=True
            )
            + "</strong>"
            if os.getenv("BUSINESS_REGISTRATION_NUMBER", "").strip()
            else ""
        ),
        "{{BUSINESS_VAT_STATUS_LINE}}": (
            "<br>VAT status: <strong>"
            + html.escape(os.getenv("BUSINESS_VAT_STATUS", ""), quote=True)
            + "</strong>"
            if os.getenv("BUSINESS_VAT_STATUS", "").strip()
            else ""
        ),
    }
    for marker, rendered_line in optional_lines.items():
        content = content.replace(marker, rendered_line)
    return HTMLResponse(content, headers={"Cache-Control": cache_control})


class ProfileRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    subjects: list = Field(default_factory=list)
    quick_select: bool = False
    year: Optional[int] = None
    student_id: Optional[str] = None
    is_eleven_plus: bool = False
    mode: Optional[str] = "homework"  # Added mode field
    question_count: Optional[int] = Field(default=None, ge=1, le=20)


class TopicMasteryPracticeRequest(BaseModel):
    subject: str
    topic_index: int = Field(..., ge=1, le=11)
    mastery_level: int = Field(..., ge=1, le=5)


class ReviewRequest(BaseModel):
    homework: str = Field(min_length=1, max_length=20_000)
    answers: str = Field(min_length=1, max_length=12_000)
    subject: str = Field(default="Maths", min_length=1, max_length=80)
    profile: Optional[dict] = None
    session_id: Optional[str] = Field(default=None, max_length=100)
    quick_review: bool = False
    uploaded_work: bool = False
    is_tutor_mode: Optional[bool] = False  # Added for tutor mode review
    from_rag: Optional[bool] = False  # Whether the question came from RAG (free)
    homework_doc_id: Optional[str] = None  # RAG document id if available
    reward_activity_id: Optional[str] = Field(default=None, max_length=100)
    question_index: Optional[int] = Field(default=None, ge=0, le=500)
    is_eleven_plus: bool = False


class ExplainDeepRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    review_feedback: Optional[str] = None
    from_rag: bool = False
    homework_doc_id: Optional[str] = None
    question_index: Optional[int] = Field(default=None, ge=0, le=500)
    is_eleven_plus: bool = False


class ImprovePracticeRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    review_feedback: Optional[str] = None
    from_rag: bool = False
    homework_doc_id: Optional[str] = None
    question_index: Optional[int] = Field(default=None, ge=0, le=500)
    is_eleven_plus: bool = False


class PhotoRequest(BaseModel):
    photo: str


class SessionUpdateRequest(BaseModel):
    homework: Optional[list] = None
    profile: Optional[dict] = None
    student_answers: Optional[str] = None
    doc_id: Optional[str] = None
    year_group: Optional[int] = None
    subject: Optional[str] = None


class FeedbackRequest(BaseModel):
    trace_id: Optional[str] = None
    score: float = Field(..., description="评分: 1.0 = thumbs up, 0.0 = thumbs down")
    name: str = Field(default="user_feedback", description="评分类型")
    comment: Optional[str] = Field(default=None, description="可选文字反馈")


class AdminUserCreateRequest(BaseModel):
    """管理员创建学生请求"""
    name: str
    year_group: int = 3
    age: int = 7


class AdminSubscriptionCreateRequest(BaseModel):
    """管理员创建订阅请求"""
    email: str
    name: str
    duration: str  # "5_days" 或 "30_days"


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    year_group: Optional[int] = None
    age: Optional[int] = None
    is_active: Optional[bool] = None


class SubscriptionRequest(BaseModel):
    email: str
    name: str
    duration: str  # "5_days" or "30_days"


class AuthRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str
    guardian_confirmed: bool = False

    def get_username(self) -> str:
        """Get username from either username or email field"""
        return (self.username or self.email or "").strip()


# --- Web routes ---


@app.get("/")
async def index(req: Request, background_tasks: BackgroundTasks):
    _count_landing_visit(req, background_tasks, "home")
    return _static_page("static", "index.html")


@app.get("/ks1-homework")
async def ks1_homework():
    return _static_page("static", "ks1-homework.html")


@app.get("/ks2-homework")
async def ks2_homework():
    return _static_page("static", "ks2-homework.html")


@app.get("/elevenplus-practice")
async def eleven_plus():
    return _static_page("static", "elevenplus-practice.html")


@app.get("/elevenplus-year-round-plan")
async def eleven_plus_year_round_plan():
    return _static_page("static", "elevenplus-year-round-plan.html")


@app.get("/elevenplus-mock-exams")
async def eleven_plus_mock_exams():
    return _static_page("static", "elevenplus-mock-exams.html")


@app.get("/elevenplus-topic-mastery")
async def eleven_plus_topic_mastery():
    return _static_page("static", "elevenplus-topic-mastery.html")


@app.get("/check-my-homework")
async def check_homework():
    return _static_page("static", "check-my-homework.html")


@app.get("/register")
async def register_page(req: Request, background_tasks: BackgroundTasks):
    _count_landing_visit(req, background_tasks, "register")
    return _static_page("static", "register.html", cache_control="no-store, private")


@app.get("/login")
async def login_page():
    return _static_page("static", "login.html", cache_control="no-store, private")


@app.get("/kid-login")
async def kid_login_page():
    return _static_page("static", "kid_login.html", cache_control="no-store, private")


@app.get("/parent-dashboard")
async def parent_dashboard_page():
    return _static_page("static", "parent_dashboard.html", cache_control="no-store, private")


@app.get("/pricing")
async def pricing_page(req: Request, background_tasks: BackgroundTasks):
    _count_landing_visit(req, background_tasks, "pricing")
    return _public_legal_page(
        "pricing.html",
        cache_control="no-store, private",
    )


@app.get("/privacy")
async def privacy_page():
    return _public_legal_page("privacy.html")


@app.get("/terms")
async def terms_page():
    return _public_legal_page("terms.html")


@app.get("/refund-policy")
async def refund_policy_page():
    return _public_legal_page("refund-policy.html")


@app.get("/safety")
async def safety_page():
    return _static_page("static", "safety.html")


@app.get("/year-3-maths-practice")
async def year_three_maths_landing(
    req: Request,
    background_tasks: BackgroundTasks,
):
    _count_landing_visit(req, background_tasks, "year3_maths")
    return _static_page("static", "year-3-maths-practice.html")


@app.get("/year-3-english-reading-practice")
async def year_three_english_landing(
    req: Request,
    background_tasks: BackgroundTasks,
):
    _count_landing_visit(req, background_tasks, "year3_english")
    return _static_page("static", "year-3-english-reading-practice.html")


@app.get("/calm-eleven-plus-practice")
async def calm_eleven_plus_landing(
    req: Request,
    background_tasks: BackgroundTasks,
):
    _count_landing_visit(req, background_tasks, "elevenplus_calm")
    return _static_page("static", "calm-eleven-plus-practice.html")


@app.get("/beta")
async def beta_page(req: Request, background_tasks: BackgroundTasks):
    _count_landing_visit(req, background_tasks, "beta")
    return _static_page(
        "static",
        "beta.html",
        cache_control="no-store, private",
    )


@app.get("/beta-feedback")
async def beta_feedback_page():
    return _static_page(
        "static",
        "beta-feedback.html",
        cache_control="no-store, private",
    )


@app.get("/progress")
async def progress_page():
    return _static_page("static", "progress.html", cache_control="no-store, private")


@app.get("/rewards")
async def rewards_page():
    return _static_page("static", "rewards.html", cache_control="no-store, private")


@app.get("/memory")
async def memory_page():
    return _static_page("static", "memory.html", cache_control="no-store, private")


@app.get("/app")
async def app_page():
    return _static_page("static", "app.html", cache_control="no-store, private")


@app.get("/year-{year}-homework")
async def year_homework_page(year: int):
    if year < 1 or year > 6:
        raise HTTPException(status_code=404, detail="Page not found")
    seo_path = os.path.join(
        project_root, "static", "--seo", f"year-{year}-homework.html"
    )
    if os.path.isfile(seo_path):
        return FileResponse(seo_path)
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/sitemap.xml")
async def sitemap():
    seo_sitemap = os.path.join(project_root, "static", "sitemap.xml")
    if os.path.isfile(seo_sitemap):
        return FileResponse(
            seo_sitemap,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    raise HTTPException(status_code=404, detail="Sitemap not found")


@app.get("/robots.txt")
async def robots():
    robots_path = os.path.join(project_root, "static", "robots.txt")
    if os.path.isfile(robots_path):
        return FileResponse(
            robots_path,
            media_type="text/plain",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    raise HTTPException(status_code=404, detail="Robots file not found")


@app.get("/contact-me", include_in_schema=False)
async def legacy_contact_page():
    return RedirectResponse("/messages", status_code=308)


@app.get(
    "/elevenplus/11plus_acceptance_rates_gcse", include_in_schema=False
)
async def legacy_acceptance_rates_page():
    return RedirectResponse(
        "/elevenplus/11plus-acceptance-rates-gcse", status_code=308
    )


@app.get(
    "/elevenplus/11plus_maths_common_mistakes", include_in_schema=False
)
async def legacy_maths_mistakes_page():
    return RedirectResponse(
        "/elevenplus/11plus-maths-common-mistake", status_code=308
    )


@app.get("/elevenplus/11plus_time_management", include_in_schema=False)
async def legacy_time_management_page():
    return RedirectResponse(
        "/elevenplus/11plus-time-management", status_code=308
    )


@app.get("/elevenplus/articles")
async def elevenplus_articles():
    return _static_page("static", "elevenplus", "articles.html")

@app.get("/elevenplus/11plus-exam-formats")
async def elevenplus_exam_formats():
    return _static_page("static", "elevenplus", "11plus-exam-formats.html")

@app.get("/elevenplus/11plus-preparation-timeline")
async def elevenplus_preparation_timeline():
    return _static_page("static", "elevenplus", "11plus-preparation-timeline.html")

@app.get("/elevenplus/11plus-acceptance-rates-gcse")
async def elevenplus_acceptance_rates_gcse():
    return _static_page("static", "elevenplus", "11plus_acceptance_rates_gcse.html")

@app.get("/elevenplus/11plus-maths-common-mistake")
async def elevenplus_math_common_mistake():
    return _static_page("static", "elevenplus", "11plus_maths_common_mistakes.html")

@app.get("/elevenplus/11plus-school-guide")
async def elevenplus_school_guide():
    return _static_page("static", "elevenplus", "11plus_school_guide.html")

@app.get("/elevenplus/11plus-time-management")
async def elevenplus_time_management():
    return _static_page("static", "elevenplus", "11plus_time_management.html")

@app.get("/elevenplus/11plus-vocabulary-list")
async def elevenplus_vocabulary_list():
    return _static_page("static", "elevenplus", "11plus_vocabulary_list.html")

@app.get("/elevenplus/comprehension-question-types")
async def elevenplus_comprehension_question_types():
    return _static_page("static", "elevenplus", "comprehension-question-types.html")

@app.get("/elevenplus/english-comprehension-strategies")
async def elevenplus_english_comprehension_strategies():
    return _static_page("static", "elevenplus", "english-comprehension-strategies.html")

@app.get("/elevenplus/essay-writing-guide")
async def elevenplus_essay_writing_guide():
    return _static_page("static", "elevenplus", "essay-writing-guide.html")

@app.get("/elevenplus/exam-day-preparation")
async def elevenplus_exam_day_preparation():
    return _static_page("static", "elevenplus", "exam-day-preparation.html")

@app.get("/elevenplus/fractions-decimals-percentages")
async def elevenplus_fractions_decimals_percentages():
    return _static_page("static", "elevenplus", "fractions-decimals-percentages.html")

@app.get("/elevenplus/geometry-algebra-fundamentals")
async def elevenplus_geometry_algebra_fundamentals():
    return _static_page("static", "elevenplus", "geometry-algebra-fundamentals.html")

@app.get("/elevenplus/managing-test-anxiety")
async def elevenplus_managing_test_anxiety():
    return _static_page("static", "elevenplus", "managing-test-anxiety.html")

@app.get("/elevenplus/maths-topics-checklist")
async def elevenplus_maths_topics_checklist():
    return _static_page("static", "elevenplus", "maths-topics-checklist.html")

@app.get("/elevenplus/mock-exam-strategy")
async def elevenplus_mock_exam_strategy():
    return _static_page("static", "elevenplus", "mock-exam-strategy.html")

@app.get("/elevenplus/non-verbal-reasoning-guide")
async def elevenplus_non_verbal_reasoning_guide():
    return _static_page("static", "elevenplus", "non-verbal-reasoning-guide.html")

@app.get("/elevenplus/problem-solving-techniques")
async def elevenplus_problem_solving_techniques():
    return _static_page("static", "elevenplus", "problem-solving-techniques.html")

@app.get("/elevenplus/revision-techniques")
async def elevenplus_revision_techniques():
    return _static_page("static", "elevenplus", "revision-techniques.html")

@app.get("/elevenplus/selective-schools-admission")
async def elevenplus_selective_schools_admission():
    return _static_page("static", "elevenplus", "selective-schools-admission.html")

@app.get("/elevenplus/spatial-awareness-practice")
async def elevenplus_spatial_awareness_practice():
    return _static_page("static", "elevenplus", "spatial-awareness-practice.html")

@app.get("/elevenplus/spelling-punctuation-grammar")
async def elevenplus_spelling_punctuation_grammar():
    return _static_page("static", "elevenplus", "spelling-punctuation-grammar.html")

@app.get("/elevenplus/stress-management-techniques")
async def elevenplus_stress_management_techniques():
    return _static_page("static", "elevenplus", "stress-management-techniques.html")

@app.get("/elevenplus/supporting-child-preparation")
async def elevenplus_supporting_child_preparation():
    return _static_page("static", "elevenplus", "supporting-child-preparation.html")

@app.get("/elevenplus/tutoring-vs-self-study")
async def elevenplus_tutoring_vs_self_study():
    return _static_page("static", "elevenplus", "tutoring-vs-self-study.html")

@app.get("/elevenplus/uk-grammar-guide")
async def elevenplus_grammar_guide():
    return _static_page("static", "elevenplus", "uk_grammar_guide.html")

@app.get("/elevenplus/verbal-reasoning-tips")
async def elevenplus_verbal_reasoning_tips():
    return _static_page("static", "elevenplus", "verbal-reasoning-tips.html")


# --- API endpoints ---


@app.get("/api/health")
async def health():
    """Lightweight liveness check; it does not call an AI provider."""
    return {"status": "ok", "initialized": initialized}


@app.get("/api/ready")
async def readiness():
    from src.progress_db import database_health_check

    issues = production_configuration_issues()
    database_ok = await run_blocking(
        database_health_check, timeout=5, limit_concurrency=False
    )
    ready = bool(database_ok and not issues)
    payload = {
        "status": "ready" if ready else "not_ready",
        "database": "ok" if database_ok else "unavailable",
        "configuration": "ok" if not issues else "needs_attention",
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@app.get("/api/client-id")
async def get_client_id(request: Request):
    """Return the cookie-backed anonymous ID without collecting or exposing an IP."""
    resolved_id, _username, new_anon_id = await _resolve_request_identity(request)
    response = JSONResponse({"client_id": resolved_id})
    if new_anon_id:
        response.set_cookie(
            "anon_session_id",
            new_anon_id,
            httponly=True,
            samesite="lax",
            secure=_cookie_should_be_secure(request),
            max_age=365 * 24 * 60 * 60,
            path="/",
        )
    return response


@app.get("/api/subjects")
async def get_subjects():
    from src.models import UK_PRIMARY_SUBJECTS, ELEVEN_PLUS_SUBJECTS

    return {
        "primary": UK_PRIMARY_SUBJECTS,
        "eleven_plus": ELEVEN_PLUS_SUBJECTS,
        "eleven_plus_year_round": [
            "Maths-1year",
            "English-1year",
            "VerbalReasoning-1year",
            "NonVerbalReasoning-1year",
        ],
        "eleven_plus_topic_mastery": list(ELEVEN_PLUS_TOPIC_MASTERY_SUBJECTS),
    }


@app.get("/api/year-groups")
async def get_year_groups():
    return {
        "year_groups": [1, 2, 3, 4, 5, 6],
        "quick_select": [
            {"year": 1, "age": 5, "stage": "KS1"},
            {"year": 2, "age": 6, "stage": "KS1"},
            {"year": 3, "age": 7, "stage": "KS2"},
            {"year": 4, "age": 8, "stage": "KS2"},
            {"year": 5, "age": 9, "stage": "KS2"},
            {"year": 6, "age": 10, "stage": "KS2"},
        ],
    }


_YEAR_ROUND_SUBJECT_MAP = {
    "Maths": "Maths-1year",
    "English": "English-1year",
    "Verbal Reasoning": "VerbalReasoning-1year",
    "VerbalReasoning": "VerbalReasoning-1year",
    "Non-Verbal Reasoning": "NonVerbalReasoning-1year",
    "Non Verbal Reasoning": "NonVerbalReasoning-1year",
    "NonVerbalReasoning": "NonVerbalReasoning-1year",
}


def _normalise_requested_subjects(subjects: List[str], profile: Dict[str, Any], is_eleven_plus: bool) -> List[str]:
    """Canonicalise and allow-list public subject labels."""
    requested_week = profile.get("plan_week")
    try:
        is_year_round = is_eleven_plus and 1 <= int(requested_week or 0) <= 52
    except (TypeError, ValueError):
        is_year_round = False
    result: List[str] = []
    for raw in subjects or []:
        label = str(raw or "").strip()
        if not label:
            continue
        if is_year_round:
            label = _YEAR_ROUND_SUBJECT_MAP.get(label, label)
            if label not in ELEVEN_PLUS_YEAR_ROUND_SUBJECTS:
                continue
        elif is_eleven_plus:
            compact_label = "".join(char for char in label.casefold() if char.isalnum())
            eleven_plus_map = {
                "maths": "Maths",
                "mathematics": "Maths",
                "english": "English",
                "verbalreasoning": "Verbal Reasoning",
                "nonverbalreasoning": "Non-Verbal Reasoning",
            }
            label = eleven_plus_map.get(compact_label, "")
            if label not in ELEVEN_PLUS_SUBJECTS:
                continue
        else:
            label = canonical_primary_subject(label)
            if not label:
                continue
        if label not in result:
            result.append(label)
    return result[:4]


def _public_homework_results(items: List[Dict[str, Any]], *, is_eleven_plus: bool) -> List[Dict[str, Any]]:
    """Build an answer-free, stable response contract for the browser."""
    public: List[Dict[str, Any]] = []
    for raw in items or []:
        item = dict(raw or {})
        content = public_homework_content(str(item.get("content") or ""))
        item["content"] = content
        item["from_rag"] = bool(item.get("from_rag", False))
        item["is_eleven_plus"] = bool(is_eleven_plus)
        questions = item.get("questions")
        if not isinstance(questions, list) or not questions:
            questions = parse_public_questions(content)
        item["questions"] = questions
        public.append(item)
    return public


def _set_anon_cookie(response: JSONResponse, anon_id: Optional[str], request: Request) -> None:
    if anon_id:
        response.set_cookie(
            "anon_session_id",
            anon_id,
            httponly=True,
            samesite="lax",
            secure=_cookie_should_be_secure(request),
            max_age=365 * 24 * 60 * 60,
            path="/",
        )

app.include_router(build_mock_exam_router(
    resolve_identity=_get_user_or_anonymous_id,
    has_subscription=user_has_subscription,
    set_anon_cookie=_set_anon_cookie,
))

@app.get("/api/elevenplus/topic-mastery/catalog")
async def get_topic_mastery_catalog():
    """Return the small static catalogue without loading RAG or an LLM."""
    from src.elevenplus_topic_mastery import topic_mastery_catalogue

    return topic_mastery_catalogue()


@app.post("/api/elevenplus/topic-mastery/practice")
async def get_topic_mastery_practice(req: Request, request: TopicMasteryPracticeRequest):
    """Fetch one exact pre-generated mastery set; never fall back to an LLM."""
    from src.elevenplus_rag import (
        format_questions_only,
        get_homework_questions,
        search_homework_by_metadata,
    )
    from src.elevenplus_topic_mastery import (
        TOPIC_MASTERY_TOPICS,
        MASTERY_LEVELS,
        mastery_set_index,
        normalise_topic_mastery_subject,
    )
    from src.models import subject_display_name

    subject_key = normalise_topic_mastery_subject(request.subject)
    if not subject_key:
        raise HTTPException(status_code=400, detail="Choose one of the available 11+ topic-mastery subjects.")

    set_index = mastery_set_index(request.topic_index, request.mastery_level)
    matches = await run_blocking(
        search_homework_by_metadata,
        6,
        subject_key,
        k=1,
        content_type="topic_mastery",
        mastery_set_index=set_index,
        timeout=12,
        limit_concurrency=False,
    )
    if not matches:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "This mastery set is not in the practice library yet. Please ask an administrator to run its topic-mastery generator.",
            },
        )

    selected = matches[0]
    content = public_homework_content(str(selected.get("content") or ""))
    questions = await run_blocking(
        get_homework_questions,
        selected.get("doc_id"),
        content,
        timeout=8,
        limit_concurrency=False,
    )
    if not questions:
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": "This practice set could not be displayed safely."},
        )

    topic = TOPIC_MASTERY_TOPICS[subject_key][request.topic_index - 1]
    level = MASTERY_LEVELS[request.mastery_level - 1]
    response = JSONResponse(
        {
            "success": True,
            "homework": [{
                "subject": subject_key,
                "subject_label": subject_display_name(subject_key),
                "content": format_questions_only(questions),
                "questions": questions,
                "doc_id": selected.get("doc_id"),
                "from_rag": True,
                "is_eleven_plus": True,
                "content_type": "topic_mastery",
                "topic": topic,
                "topic_index": request.topic_index,
                "mastery_level": request.mastery_level,
                "mastery_level_name": level["name"],
                "mastery_set_index": set_index,
            }],
        }
    )
    _resolved_id, _username, new_anon_session_id = await _resolve_request_identity(req)
    _set_anon_cookie(response, new_anon_session_id, req)
    return response


@app.post("/api/generate")
async def api_generate(req: Request, request: ProfileRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = await _resolve_request_identity(req)

        request.student_id = resolved_student_id
        request.profile = dict(request.profile or {})
        request.profile["student_id"] = resolved_student_id
        setup_source = str(request.profile.get("setup_source") or "").strip()
        if request.question_count is not None:
            request.profile["question_count"] = request.question_count
        if setup_source == "guided_homework":
            request.profile = normalise_guided_homework_profile(
                request.profile, resolved_student_id
            )
        elif setup_source == "guided_11plus":
            request.profile = normalise_guided_eleven_profile(
                request.profile, resolved_student_id
            )

        description_for_safety = str(request.profile.get("description") or "").strip()
        concern = detect_safeguarding_concern(description_for_safety)
        if concern is not None:
            return JSONResponse(content={
                "success": False,
                "error": concern.message,
                "safety_intervention": True,
                "safety_category": concern.category,
            })
        if (
            not request.subjects
            and not request.is_eleven_plus
            and description_for_safety
            and not extract_primary_subjects(description_for_safety)
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": OUT_OF_SCOPE_HOMEWORK_MESSAGE,
                    "policy_blocked": True,
                },
            )
        profile = resolve_profile(
            request.profile,
            quick_select=request.quick_select,
            year=request.year,
            student_id=resolved_student_id,
        )

        subjects = list(request.subjects or [])
        if setup_source in {"guided_homework", "guided_11plus"}:
            subjects = [profile["subject"]]
        if not subjects:
            description = str(request.profile.get("description") or profile.get("description") or "").strip()
            if description:
                from src.ui.shared import parse_profile_from_natural_language

                # Personalised homework is a closed learning feature, not a
                # general chat endpoint.  Resolve a supported primary subject
                # locally before any model call so unrelated requests cannot be
                # answered or turned into an arbitrary homework subject.
                extracted_primary_subjects = (
                    [] if request.is_eleven_plus else extract_primary_subjects(description)
                )
                if not request.is_eleven_plus and not extracted_primary_subjects:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "error": OUT_OF_SCOPE_HOMEWORK_MESSAGE,
                            "policy_blocked": True,
                        },
                    )

                parsed = await run_blocking(
                    parse_profile_from_natural_language,
                    description,
                    llm,
                    profile.get("year_group") or request.year,
                    timeout=20,
                )
                if parsed:
                    profile.update(parsed)
                    profile["student_id"] = resolved_student_id
                    subjects = extracted_primary_subjects or list(parsed.get("extracted_subjects") or [])
            if not subjects:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "Please choose a subject, or tell us the year group and subject.",
                    },
                )

        subjects = _normalise_requested_subjects(subjects, profile, request.is_eleven_plus)
        if not subjects:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": OUT_OF_SCOPE_HOMEWORK_MESSAGE,
                    "policy_blocked": True,
                },
            )

        is_year_round = bool(request.is_eleven_plus) and (
            _is_eleven_plus_year_round(profile)
            or any(_is_eleven_plus_year_round(subject=subject) for subject in subjects)
        )
        if is_year_round or setup_source == "guided_11plus":
            required_plan = ELEVENPLUS_PREMIUM_PLAN
            has_sub = await run_blocking(
                user_has_subscription,
                req,
                resolved_student_id,
                logged_in_username,
                required_plan,
                timeout=12,
                limit_concurrency=False,
            )
            if not has_sub:
                return _subscription_required_response(
                    (
                        "11+ guided practice"
                        if setup_source == "guided_11plus"
                        else "11+ year-round practice"
                    ),
                    required_plan,
                    logged_in_username,
                    resolved_student_id,
                )

        generated = await run_blocking(
            generate_homework_with_profile,
            profile,
            subjects,
            request.is_eleven_plus,
            timeout=120,
        )
        all_homework_results = _public_homework_results(generated, is_eleven_plus=request.is_eleven_plus)
        if setup_source in {"guided_homework", "guided_11plus"}:
            all_homework_results = limit_homework_question_count(
                all_homework_results, profile["question_count"]
            )
        # A short server-issued activity ID lets the reward system distinguish
        # a newly generated activity from a repeated submission of the same
        # activity. This matters when RAG selects the same source document more
        # than once. It contains no learner or homework data and is still
        # protected by the daily XP cap.
        for homework_block in all_homework_results:
            homework_block["reward_activity_id"] = f"act_{uuid.uuid4().hex}"
        if setup_source == "guided_homework":
            response_profile = guided_homework_client_profile(profile)
        elif setup_source == "guided_11plus":
            response_profile = guided_eleven_client_profile(profile)
        else:
            response_profile = profile

        if request.mode == "tutor":
            individual_questions: List[Dict[str, Any]] = []
            for hw_block in all_homework_results:
                split_questions = _split_homework_into_questions(
                    hw_block.get("content", ""), hw_block.get("subject", "Maths")
                )
                for question_index, question in enumerate(split_questions):
                    question["doc_id"] = hw_block.get("doc_id")
                    question["from_rag"] = bool(hw_block.get("from_rag", False))
                    question["is_eleven_plus"] = bool(request.is_eleven_plus)
                    question["question_index"] = question_index
                    question["reward_activity_id"] = hw_block.get(
                        "reward_activity_id"
                    )
                    question["plan_week"] = hw_block.get("plan_week") or profile.get("plan_week")
                    question["content_type"] = hw_block.get("content_type")
                individual_questions.extend(split_questions)

            required_plan = _required_premium_plan(
                is_eleven_plus=bool(request.is_eleven_plus), profile=profile
            )
            has_sub = await run_blocking(
                user_has_subscription,
                req,
                resolved_student_id,
                logged_in_username,
                required_plan,
                timeout=12,
                limit_concurrency=False,
            )
            if not has_sub:
                rag_only = [item for item in individual_questions if item.get("from_rag")]
                if rag_only:
                    response = JSONResponse({
                        "success": True,
                        "homework": rag_only,
                        "profile": response_profile,
                        "mode": "tutor",
                        "note": "Library questions are available. A subscription is needed for newly generated tutor questions.",
                    })
                    _set_anon_cookie(response, new_anon_session_id, req)
                    return response
                return _subscription_required_response(
                    "Tutor mode", required_plan, logged_in_username, resolved_student_id
                )

            response = JSONResponse({
                "success": True,
                "homework": individual_questions,
                "profile": response_profile,
                "mode": "tutor",
            })
            _set_anon_cookie(response, new_anon_session_id, req)
            return response

        response = JSONResponse({
            "success": True,
            "homework": all_homework_results,
            "profile": response_profile,
            "mode": "homework",
        })
        _set_anon_cookie(response, new_anon_session_id, req)
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Homework generation failed")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not make the homework just now. Please try again."},
        )


@app.post("/api/review")
async def api_review(
    req: Request,
    request_body: ReviewRequest,
    background_tasks: BackgroundTasks,
):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = await _resolve_request_identity(req)
        profile = dict(request_body.profile or {})
        profile["student_id"] = resolved_student_id

        if request_body.session_id:
            session_owner = owner_key(logged_in_username or resolved_student_id)
            session = await run_blocking(
                tutor_session_store.get,
                request_body.session_id,
                session_owner,
                timeout=5,
                limit_concurrency=False,
            )
            if session:
                profile = {**session.get("profile", {}), **profile}

        is_year_round_review = _is_eleven_plus_year_round(profile, request_body.subject)
        uses_quick_model = bool(
            request_body.quick_review
            and not request_body.is_tutor_mode
            and not is_year_round_review
        )
        uses_detail_model = not uses_quick_model
        requires_premium_review = bool(request_body.uploaded_work or uses_detail_model)
        free_rag_tutor_review = bool(
            request_body.is_tutor_mode
            and request_body.from_rag
            and request_body.homework_doc_id
        )
        if requires_premium_review and not free_rag_tutor_review:
            required_plan = _required_premium_plan(
                is_eleven_plus=bool(request_body.is_eleven_plus),
                profile=profile,
                subject=request_body.subject,
            )
            has_sub = await run_blocking(
                user_has_subscription,
                req,
                resolved_student_id,
                logged_in_username,
                required_plan,
                timeout=12,
                limit_concurrency=False,
            )
            if not has_sub:
                if request_body.is_tutor_mode:
                    feature = "Review Question"
                elif request_body.uploaded_work:
                    feature = "Mark uploaded homework"
                elif is_year_round_review:
                    feature = "11+ year-round review"
                else:
                    feature = "Detailed review"
                return _subscription_required_response(feature, required_plan, logged_in_username, resolved_student_id)

        result = await run_blocking(
            review_homework,
            request_body.homework,
            request_body.answers,
            request_body.subject,
            profile,
            quick_review=bool(request_body.quick_review),
            uploaded_work=bool(request_body.uploaded_work),
            is_tutor_mode=bool(request_body.is_tutor_mode),
            homework_doc_id=request_body.homework_doc_id,
            is_eleven_plus=bool(request_body.is_eleven_plus),
            question_index=request_body.question_index,
            timeout=120,
        )
        # 奖励发放：家长登录或孩子登录都可以获得 XP
        should_award = (
            (logged_in_username or resolved_student_id)
            and result.get("success")
            and not result.get("safety_intervention")
        )
        # 排除匿名用户（student_id 以 anon_ 开头）
        if should_award and str(resolved_student_id).startswith("anon_"):
            should_award = False

        if should_award:
            try:
                from src.webapp.account_store import (
                    ensure_account,
                    get_student,
                    student_belongs_to_account,
                )
                from src.webapp.reward_store import (
                    get_reward_store,
                    review_fingerprint,
                )

                # 解析 account：家长登录用 email，孩子登录用 student 的 account_id
                account = None
                if logged_in_username:
                    account = await run_blocking(
                        ensure_account,
                        logged_in_username,
                        timeout=10,
                        limit_concurrency=False,
                    )
                else:
                    # 孩子登录会话：通过 student_id 找到 account
                    student = await run_blocking(
                        get_student,
                        resolved_student_id,
                        timeout=10,
                        limit_concurrency=False,
                    )
                    if student and student.get("account_id"):
                        from src.webapp.account_store import get_account
                        account = await run_blocking(
                            get_account,
                            str(student["account_id"]),
                            timeout=10,
                            limit_concurrency=False,
                        )

                if not account:
                    raise ValueError("Could not resolve account for reward")

                owns_learner, gift_points_eligible = await asyncio.gather(
                    run_blocking(
                        student_belongs_to_account,
                        resolved_student_id,
                        account["id"],
                        timeout=10,
                        limit_concurrency=False,
                    ),
                    _account_has_reward_subscription(account["id"]),
                )
                if owns_learner:
                    fingerprint = review_fingerprint(
                        homework=request_body.homework,
                        answers=request_body.answers,
                        subject=request_body.subject,
                        reward_activity_id=request_body.reward_activity_id,
                        homework_doc_id=request_body.homework_doc_id,
                        question_index=request_body.question_index,
                        session_id=request_body.session_id,
                    )
                    # 根据正确率计算额外奖励 XP
                    score_val = result.get("score")
                    max_score_val = result.get("max_score")
                    # accuracy_bonus_xp = 0
                    accuracy = None
                    if (
                        isinstance(score_val, (int, float))
                        and isinstance(max_score_val, (int, float))
                        and max_score_val > 0
                    ):
                        accuracy = score_val / max_score_val
                        # if accuracy >= 1.0:
                        #     accuracy_bonus_xp = 10
                        # elif accuracy >= 0.8:
                        #     accuracy_bonus_xp = 5
                    reward_update = await run_blocking(
                        get_reward_store().award_checked_activity,
                        account_id=account["id"],
                        student_id=resolved_student_id,
                        fingerprint=fingerprint,
                        subject=request_body.subject,
                        is_tutor_mode=bool(request_body.is_tutor_mode),
                        gift_points_eligible=gift_points_eligible,
                        accuracy=accuracy,
                        timeout=10,
                        limit_concurrency=False,
                    )
                    result = {**result, "reward_update": reward_update}
                    if reward_update.get("is_first_family_activity"):
                        background_tasks.add_task(
                            record_marketing_event,
                            "first_activity_completed",
                            source="unknown",
                            page="learning_app",
                        )
                    if (
                        reward_update.get("is_first_family_return_day")
                        and _within_first_seven_days(account.get("created_at"))
                    ):
                        background_tasks.add_task(
                            record_marketing_event,
                            "return_within_7_days",
                            source="unknown",
                            page="learning_app",
                        )
            except Exception:
                # Reward persistence must never turn successful homework marking
                # into an error for a child.
                logger.exception("Could not award homework quest XP")
        response = JSONResponse(content=result)
        _set_anon_cookie(response, new_anon_session_id, req)
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Homework review failed")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not check the answers just now. Please try again."},
        )


@app.post("/api/explain-deep")
async def api_explain_deep(req: Request, request_body: ExplainDeepRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = await _resolve_request_identity(req)

        profile = dict(request_body.profile or {})
        profile["student_id"] = resolved_student_id
        required_plan = _required_premium_plan(
            is_eleven_plus=bool(request_body.is_eleven_plus),
            profile=profile,
            subject=request_body.subject,
        )
        has_sub = await run_blocking(
            user_has_subscription,
            req,
            resolved_student_id,
            logged_in_username,
            required_plan,
            timeout=12,
            limit_concurrency=False,
        )
        if not has_sub:
            return _subscription_required_response(
                "Explain in Detail", required_plan, logged_in_username, resolved_student_id
            )
        result = await run_blocking(
            explain_deep,
            request_body.homework,
            request_body.answers,
            request_body.subject,
            profile,
            request_body.review_feedback or "",
            homework_doc_id=request_body.homework_doc_id,
            is_eleven_plus=bool(request_body.is_eleven_plus),
            question_index=request_body.question_index,
            timeout=120,
        )
        response = JSONResponse(content=result)
        _set_anon_cookie(response, new_anon_session_id, req)
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Detailed explanation failed")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not make the explanation just now. Please try again."},
        )


@app.post("/api/improve-practice")
async def api_improve_practice(req: Request, request_body: ImprovePracticeRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = await _resolve_request_identity(req)
        profile = dict(request_body.profile or {})
        profile["student_id"] = resolved_student_id
        required_plan = _required_premium_plan(
            is_eleven_plus=bool(request_body.is_eleven_plus),
            profile=profile,
            subject=request_body.subject,
        )
        has_sub = await run_blocking(
            user_has_subscription,
            req,
            resolved_student_id,
            logged_in_username,
            required_plan,
            timeout=12,
            limit_concurrency=False,
        )
        if not has_sub:
            return _subscription_required_response(
                "Help me improve", required_plan, logged_in_username, resolved_student_id
            )
        result = await run_blocking(
            improve_practice,
            request_body.homework,
            request_body.answers,
            request_body.subject,
            profile,
            request_body.review_feedback or "",
            homework_doc_id=request_body.homework_doc_id,
            is_eleven_plus=bool(request_body.is_eleven_plus),
            question_index=request_body.question_index,
            timeout=120,
        )
        response = JSONResponse(
            status_code=502 if result.get("llm_no_response") else 200,
            content=result,
        )
        _set_anon_cookie(response, new_anon_session_id, req)
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Practice generation failed")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": (
                    "The AI tutor could not generate extra practice content just now. "
                    "Please try again in a moment."
                ),
                "llm_no_response": True,
            },
        )


@app.get("/api/progress")
@app.get("/api/progress/{student_id}")
async def api_get_progress(
    req: Request,
    student_id: Optional[str] = None,
    subject: Optional[str] = None,
):
    """Get progress for the signed-in account's selected/default learner.

    ``static/progress.html`` calls ``/api/progress`` without a learner ID.
    Existing family-account clients may still call ``/api/progress/{student_id}``.
    Both routes use the same account-ownership and subscription checks.
    """
    try:
        resolved_student_id, logged_in_username, _ = await _resolve_request_identity(req)

        # 孩子登录会话：只能查看自己的进度
        is_kid_session = False
        if logged_in_username is None:
            kid_token = req.cookies.get("kid_session") or req.headers.get("X-Kid-Session")
            if kid_token:
                from src.webapp.kid_session_store import resolve_kid_session
                kid_session = await run_blocking(resolve_kid_session, kid_token, timeout=10, limit_concurrency=False)
                if kid_session:
                    is_kid_session = True
                    resolved_student_id = str(kid_session["student_id"])
            if not is_kid_session:
                return JSONResponse(status_code=401, content={"success": False, "error": "Login required to view progress."})

        target_student_id = str(student_id or resolved_student_id).strip()
        if not target_student_id:
            return JSONResponse(status_code=400, content={"success": False, "error": "A learner profile is required."})

        # 孩子会话只能查看自己的进度，家长可查看所属孩子的进度
        from src.webapp.account_store import student_belongs_to_account
        if is_kid_session:
            if target_student_id != resolved_student_id:
                return JSONResponse(status_code=403, content={"success": False, "error": "Access denied to this learner's progress."})
        else:
            from src.webapp.account_store import ensure_account
            account = await run_blocking(ensure_account, logged_in_username, timeout=10, limit_concurrency=False)
            belongs = await run_blocking(
                student_belongs_to_account, target_student_id, account["id"], timeout=10, limit_concurrency=False
            )
            if not belongs:
                return JSONResponse(status_code=403, content={"success": False, "error": "Access denied to this learner's progress."})

        if not user_has_subscription(req=req, student_id=target_student_id, username=logged_in_username):
            return JSONResponse(status_code=402, content={"success": False,
                                                          "error": "Progress tracking requires an active subscription."})

        from src.progress_db import (
            get_progress_summary,
            get_score_history,
            get_topic_progress,
            get_daily_goal_stats,
            get_streak_info,
            get_accuracy_rate,
            generate_progress_feedback,
        )

        # 获取原始数据
        raw_summary = await asyncio.to_thread(get_progress_summary, target_student_id)
        score_history = await asyncio.to_thread(get_score_history, target_student_id, subject)
        topics = await asyncio.to_thread(get_topic_progress, target_student_id, subject)

        # 新增指标
        daily_goal = await asyncio.to_thread(get_daily_goal_stats, target_student_id)
        streak = await asyncio.to_thread(get_streak_info, target_student_id)
        accuracy = await asyncio.to_thread(get_accuracy_rate, target_student_id)

        # 转换为前端期望的格式
        total_sessions = raw_summary.get("total_sessions", 0)
        avg_accuracy_pct = round(float(raw_summary.get("average_accuracy") or 0), 1)

        # 转换科目数据
        by_subject = []
        for subj in raw_summary.get("subjects", []):
            by_subject.append({
                "subject": subj["subject"],
                "avg_accuracy": round(float(subj.get("avg_accuracy") or 0), 1),
                "total_sessions": subj["count"],
            })

        # 转换分数历史
        score_history_formatted = []
        for s in score_history:
            score_val = s.get("score", 0) or 0
            score_history_formatted.append({
                "subject": s.get("subject", ""),
                "score": score_val,
                "max_score": s.get("max_score", 10) or 10,
                "created_at": s.get("created_at", ""),
            })

        # 生成鼓励性反馈
        feedback = generate_progress_feedback(
            total_sessions=total_sessions,
            avg_accuracy=avg_accuracy_pct,
            current_streak=streak["current_streak"],
            daily_goal_rate=daily_goal["daily_goal_rate"],
        )

        return {
            "success": True,
            "summary": {
                "overall": {
                    "total_sessions": total_sessions,
                    "avg_accuracy": avg_accuracy_pct,
                },
                "by_subject": by_subject,
            },
            "score_history": score_history_formatted,
            "topics": topics,
            "daily_goal": daily_goal,
            "streak": streak,
            "accuracy_rate": accuracy,
            "feedback": feedback,
        }
    except Exception:
        logger.exception("Error getting progress")
        return JSONResponse(
            status_code=500, content={"success": False, "error": "We could not load progress just now. Please try again."}
        )


@app.get("/api/quick-profile/{year}")
async def get_quick_profile(year: int):
    from src.models import SAMPLE_STUDENT_PROFILES

    student_id = f"student_{year}"
    profile = SAMPLE_STUDENT_PROFILES.get(
        student_id,
        {"year_group": year, "age": 5 + (year - 1), "student_id": student_id},
    )
    return {"success": True, "profile": profile}


async def _request_session_owner(request: Request) -> tuple[str, Optional[str]]:
    resolved_id, username, new_anon_id = await _resolve_request_identity(request)
    return owner_key(username or resolved_id), new_anon_id


@app.post("/api/sessions")
async def create_session(request: Request):
    session_owner, new_anon_id = await _request_session_owner(request)
    payload = {
        "homework": [],
        "profile": {},
        "student_answers": "",
        "doc_id": "",
        "year_group": 3,
        "subject": "Maths",
    }
    session = await asyncio.to_thread(tutor_session_store.create, session_owner, payload)
    response = JSONResponse({"success": True, "session_id": session["session_id"]})
    if new_anon_id:
        response.set_cookie(
            "anon_session_id", new_anon_id, httponly=True, samesite="lax",
            secure=not _dev_mode, max_age=365 * 24 * 60 * 60,
        )
    return response


@app.get("/api/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    session_owner, _ = await _request_session_owner(request)
    session = await asyncio.to_thread(tutor_session_store.get, session_id, session_owner)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.put("/api/sessions/{session_id}")
async def update_session(request: Request, session_id: str, body: SessionUpdateRequest):
    session_owner, _ = await _request_session_owner(request)
    updates = body.model_dump(exclude_unset=True)
    try:
        session = await asyncio.to_thread(
            tutor_session_store.update, session_id, session_owner, updates
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="Session changed; please reload") from exc
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.delete("/api/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    session_owner, _ = await _request_session_owner(request)
    deleted = await asyncio.to_thread(tutor_session_store.delete, session_id, session_owner)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@app.post("/api/create-subscription")
async def create_subscription(req: Request, request: SubscriptionRequest):
    """Legacy local-only helper.

    Real production billing is handled by ``/api/billing/checkout`` and signed
    Stripe webhooks. This route cannot create a production entitlement.
    """
    if not _dev_mode:
        raise HTTPException(
            status_code=410,
            detail="This billing route is retired. Please use the secure checkout page.",
        )
    username = _resolve_username(req)
    if not username:
        raise HTTPException(status_code=401, detail="A parent or guardian must sign in.")
    duration_days = {"5_days": 5, "30_days": 30}
    if request.duration not in duration_days:
        raise HTTPException(status_code=400, detail="Please choose a valid test duration.")
    from src.progress_db import create_local_subscription

    product_name = "5-Day Test Access" if request.duration == "5_days" else "30-Day Test Access"
    result = await run_blocking(
        create_local_subscription,
        customer_email=username,
        customer_name="Test account",
        product_name=product_name,
        duration_days=duration_days[request.duration],
        timeout=10,
        limit_concurrency=False,
    )
    return {
        "success": True,
        "subscription_id": result["subscription_id"],
        "product_name": product_name,
        "duration": request.duration,
        "test_mode": True,
    }


@app.get("/api/check-subscription")
async def check_subscription_api(req: Request, plan: Optional[str] = None):
    resolved_student_id, logged_in_username, new_anon_session_id = await _resolve_request_identity(req)
    required_plan = plan if plan in PREMIUM_PLAN_NAMES else None
    has_sub = await run_blocking(
        user_has_subscription,
        req,
        resolved_student_id,
        logged_in_username,
        required_plan,
        timeout=12,
        limit_concurrency=False,
    )
    response = JSONResponse({
        "has_subscription": bool(has_sub),
        "logged_in": logged_in_username is not None,
        "required_plan": required_plan,
        "required_plan_name": PREMIUM_PLAN_NAMES.get(required_plan) if required_plan else None,
    })
    _set_anon_cookie(response, new_anon_session_id, req)
    return response


@app.get("/api/check-parent-status")
async def check_parent_status_api(req: Request):
    """Check if the logged-in user is a parent (has children associated with their account)."""
    resolved_student_id, logged_in_username, new_anon_session_id = await _resolve_request_identity(req)
    
    is_parent = False
    child_count = 0
    
    if logged_in_username:
        # Import here to avoid circular imports
        from src.webapp.account_store import get_account_by_email, list_students
        
        account = await run_blocking(get_account_by_email, logged_in_username, timeout=10, limit_concurrency=False)
        if account:
            students = await run_blocking(list_students, account["id"], timeout=10, limit_concurrency=False)
            child_count = len(students)
            is_parent = child_count > 0
    
    response = JSONResponse({
        "is_parent": is_parent,
        "child_count": child_count,
        "logged_in": logged_in_username is not None,
    })
    _set_anon_cookie(response, new_anon_session_id, req)
    return response


def _public_session_student(student: Dict[str, Any]) -> Dict[str, Any]:
    """Return only learner fields that are safe for role-aware navigation."""
    return {
        "id": str(student.get("id") or ""),
        "name": str(student.get("name") or "Learner"),
        "year_group": int(student.get("year_group") or 1),
        "age": int(student.get("age") or 5),
        "is_default": bool(student.get("is_default")),
    }


@app.get("/api/session-context")
async def session_context_api(req: Request):
    """Return the authoritative browser role without exposing login codes."""
    kid_token = req.cookies.get("kid_session") or req.headers.get("X-Kid-Session")
    if kid_token:
        from src.webapp.kid_session_store import resolve_kid_session
        from src.webapp.account_store import get_student

        kid_session = await run_blocking(
            resolve_kid_session, kid_token, timeout=10, limit_concurrency=False
        )
        if kid_session:
            learner = await run_blocking(
                get_student,
                str(kid_session["student_id"]),
                timeout=10,
                limit_concurrency=False,
            )
            if learner and bool(learner.get("is_active")):
                context = {
                    "authenticated": True,
                    "role": "kid",
                    "student": _public_session_student(learner),
                }
                try:
                    from src.webapp.reward_store import get_reward_store

                    context["avatar"] = await run_blocking(
                        get_reward_store().avatar_summary,
                        account_id=str(learner["account_id"]),
                        student_id=str(learner["id"]),
                        timeout=3,
                        limit_concurrency=False,
                    )
                except Exception:
                    # Navigation and kid login must remain available if the
                    # optional reward/avatar lookup is temporarily unavailable.
                    logger.exception("Could not load the learner avatar summary")
                return context

    username = _resolve_username(req)
    if username:
        from src.webapp.account_store import (
            adjust_student_for_academic_year,
            ensure_account,
            ensure_default_student,
            get_student_limit,
            list_students,
        )

        account = await run_blocking(
            ensure_account, username, timeout=10, limit_concurrency=False
        )
        await run_blocking(
            ensure_default_student,
            account["id"],
            timeout=10,
            limit_concurrency=False,
        )
        students = await run_blocking(
            list_students,
            account["id"],
            True,
            timeout=10,
            limit_concurrency=False,
        )
        public_students = [
            _public_session_student(adjust_student_for_academic_year(item))
            for item in students
        ]
        default_student = next(
            (item["id"] for item in public_students if item["is_default"]),
            public_students[0]["id"] if public_students else None,
        )
        student_limit = await run_blocking(
            get_student_limit,
            account["id"],
            timeout=10,
            limit_concurrency=False,
        )
        return {
            "authenticated": True,
            "role": "parent",
            "students": public_students,
            "default_student_id": default_student,
            "student_limit": int(student_limit),
        }

    return {"authenticated": False, "role": "anonymous"}


_COMMON_PASSWORDS = {
    "password", "password1", "password123", "qwerty123", "letmein123",
    "homework123", "12345678", "123456789", "welcome123",
}


def _password_error(password: str) -> Optional[str]:
    minimum = 8 if (_dev_mode or os.getenv("TESTING", "").lower() in {"1", "true", "yes"}) else 10
    if len(password or "") < minimum:
        return f"Password must be at least {minimum} characters long."
    if len(password) > 128:
        return "Password is too long."
    if password.casefold() in _COMMON_PASSWORDS:
        return "Please choose a less common password."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Use a mix of letters and numbers."
    return None


@app.post("/api/register")
async def api_register(request_body: AuthRequest, req: Request, background_tasks: BackgroundTasks):
    try:
        from src.progress_db import create_user
        from src.auth_tokens import generate_token
        from src.webapp.account_store import ensure_account, ensure_default_student

        username = request_body.get_username().lower()
        password = request_body.password or ""
        if not username:
            return JSONResponse(status_code=400, content={"success": False, "error": "A parent or guardian email address is required."})
        if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", username):
            return JSONResponse(status_code=400, content={"success": False, "error": "Please enter a valid parent or guardian email address."})
        password_error = _password_error(password)
        if password_error:
            return JSONResponse(status_code=400, content={"success": False, "error": password_error})
        if not (_dev_mode or os.getenv("TESTING", "").lower() in {"1", "true", "yes"}) and not request_body.guardian_confirmed:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "A parent or guardian must confirm that they are creating this family account.",
                },
            )

        try:
            await run_blocking(create_user, username, password, timeout=15, limit_concurrency=False)
        except ValueError as exc:
            if "already exists" in str(exc).lower():
                return JSONResponse(status_code=400, content={"success": False, "error": "This email is already registered. Please sign in instead."})
            return JSONResponse(status_code=400, content={"success": False, "error": "We could not create that account."})

        account = await run_blocking(ensure_account, username, timeout=10, limit_concurrency=False)
        await run_blocking(ensure_default_student, account["id"], timeout=10, limit_concurrency=False)
        token = await run_blocking(generate_token, username, timeout=10, limit_concurrency=False)
        background_tasks.add_task(send_registration_confirmation_email, to_email=username)
        background_tasks.add_task(
            record_marketing_event,
            "parent_account_created",
            source=_marketing_source(req),
            page="register",
        )
        response = JSONResponse({"success": True})
        response.set_cookie(
            "session", token, httponly=True, samesite="lax",
            secure=_cookie_should_be_secure(req), path="/", max_age=12 * 60 * 60,
        )
        kid_token = req.cookies.get("kid_session")
        if kid_token:
            from src.webapp.kid_session_store import revoke_kid_session
            await run_blocking(
                revoke_kid_session, kid_token, timeout=10, limit_concurrency=False
            )
        response.delete_cookie(
            "kid_session", path="/", httponly=True, samesite="lax",
            secure=_cookie_should_be_secure(req),
        )
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Registration failed")
        return JSONResponse(status_code=500, content={"success": False, "error": "We could not create the account just now. Please try again."})


@app.post("/api/login")
async def api_login(request_body: AuthRequest, req: Request):
    try:
        from src.progress_db import verify_user_credentials
        from src.auth_tokens import generate_token

        username = request_body.get_username().lower()
        password = request_body.password or ""
        if not username or not password:
            return JSONResponse(status_code=400, content={"success": False, "error": "Enter the email address and password."})
        ok = await run_blocking(verify_user_credentials, username, password, timeout=15, limit_concurrency=False)
        if not ok:
            return JSONResponse(status_code=401, content={"success": False, "error": "The email address or password is not correct."})
        token = await run_blocking(generate_token, username, timeout=10, limit_concurrency=False)
        response = JSONResponse({"success": True})
        response.set_cookie(
            "session", token, httponly=True, samesite="lax",
            secure=_cookie_should_be_secure(req), path="/", max_age=12 * 60 * 60,
        )
        kid_token = req.cookies.get("kid_session")
        if kid_token:
            from src.webapp.kid_session_store import revoke_kid_session
            await run_blocking(
                revoke_kid_session, kid_token, timeout=10, limit_concurrency=False
            )
        response.delete_cookie(
            "kid_session", path="/", httponly=True, samesite="lax",
            secure=_cookie_should_be_secure(req),
        )
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Login failed")
        return JSONResponse(status_code=500, content={"success": False, "error": "We could not sign you in just now. Please try again."})


@app.post("/api/logout")
async def api_logout(req: Request):
    token = req.cookies.get("session") or req.headers.get("Authorization")
    if token:
        try:
            from src.auth_tokens import revoke_token
            await run_blocking(revoke_token, token, timeout=10, limit_concurrency=False)
        except Exception:
            logger.exception("Could not revoke logout token")
    response = JSONResponse({"success": True})
    response.delete_cookie(
        "session", path="/", httponly=True, samesite="lax",
        secure=_cookie_should_be_secure(req),
    )
    kid_token = req.cookies.get("kid_session")
    if kid_token:
        try:
            from src.webapp.kid_session_store import revoke_kid_session
            await run_blocking(
                revoke_kid_session, kid_token, timeout=10, limit_concurrency=False
            )
        except Exception:
            logger.exception("Could not revoke overlapping kid session")
    response.delete_cookie(
        "kid_session", path="/", httponly=True, samesite="lax",
        secure=_cookie_should_be_secure(req),
    )
    return response


class KidLoginRequest(BaseModel):
    family_code: str = Field(default="")
    kid_code: str = Field(default="")
    # 组合登录码: family_body-kid_body (例如 7RQKF6-EBRHWY 或 7RQKF6-EBR)
    login_code: str = Field(default="")


@app.post("/api/kid-login")
async def api_kid_login(request_body: KidLoginRequest, req: Request):
    """孩子使用组合登录码或 family_code + kid_code 登录。"""
    try:
        from src.webapp.account_store import verify_family_kid_codes, verify_combined_login_code
        from src.webapp.kid_session_store import create_kid_session

        login_code = str(request_body.login_code or "").strip()
        family_code = str(request_body.family_code or "").strip()
        kid_code = str(request_body.kid_code or "").strip()

        # 优先使用组合登录码
        if login_code:
            student = await run_blocking(
                verify_combined_login_code, login_code,
                timeout=10, limit_concurrency=False,
            )
        elif family_code and kid_code:
            student = await run_blocking(
                verify_family_kid_codes, family_code, kid_code,
                timeout=10, limit_concurrency=False,
            )
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Please enter your login code."},
            )
        if not student:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "The codes are not correct. Please check and try again."},
            )
        session = await run_blocking(
            create_kid_session, student["id"], 3600,
            timeout=10, limit_concurrency=False,
        )
        response = JSONResponse({
            "success": True,
            "student_id": student["id"],
            "student_name": student.get("name", ""),
            "token": session["token"],
        })
        response.set_cookie(
            "kid_session", session["token"], httponly=True, samesite="lax",
            secure=_cookie_should_be_secure(req), path="/", max_age=3600,
        )
        parent_token = req.cookies.get("session") or req.headers.get("Authorization")
        if parent_token:
            from src.auth_tokens import revoke_token
            await run_blocking(
                revoke_token, parent_token, timeout=10, limit_concurrency=False
            )
        response.delete_cookie(
            "session", path="/", httponly=True, samesite="lax",
            secure=_cookie_should_be_secure(req),
        )
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Kid login failed")
        return JSONResponse(status_code=500, content={"success": False, "error": "We could not sign you in just now."})


@app.post("/api/kid-logout")
async def api_kid_logout(req: Request):
    """撤销孩子的登录会话。"""
    token = req.cookies.get("kid_session") or req.headers.get("X-Kid-Session")
    if token:
        try:
            from src.webapp.kid_session_store import revoke_kid_session
            await run_blocking(revoke_kid_session, token, timeout=10, limit_concurrency=False)
        except Exception:
            logger.exception("Could not revoke kid session")
    response = JSONResponse({"success": True})
    response.delete_cookie(
        "kid_session", path="/", httponly=True, samesite="lax",
        secure=_cookie_should_be_secure(req),
    )
    return response


@app.post("/api/upload-file")
async def upload_file(request: Request, file: UploadFile = File(...)):
    try:
        initialize()
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        allowed_all = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_TEXT_EXTENSIONS | ALLOWED_PDF_EXTENSION
        filepath = await stream_upload_to_temp(
            file,
            allowed_extensions=allowed_all,
            max_bytes=MAX_UPLOAD_BYTES,
            directory=UPLOAD_FOLDER,
        )
        is_image_upload = normalised_extension(file.filename) in ALLOWED_IMAGE_EXTENSIONS
        try:
            content, is_image = await run_blocking(
                process_uploaded_file,
                filepath,
                timeout=90 if is_image_upload else 30,
                limit_concurrency=is_image_upload,
            )
        except HTTPException as exc:
            # A 503 occurs before the worker starts, so it still owns no file.
            # On a 504 the worker continues safely and removes the file itself.
            if exc.status_code == 503:
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            raise
        return {"success": True, "content": content, "is_image": is_image}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Error uploading file")
        raise HTTPException(status_code=500, detail="We could not read that file. Please try another one.")


@app.post("/api/upload-photo")
async def upload_photo(request: Request, request_body: PhotoRequest):
    try:
        initialize()

        if not request_body.photo:
            raise HTTPException(status_code=400, detail="No photo data")

        content = await run_blocking(process_base64_image, request_body.photo, timeout=90)
        return {"success": True, "content": content}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Error uploading photo")
        raise HTTPException(status_code=500, detail="We could not read that photo. Please try again.")


@app.post("/api/feedback")
async def api_feedback(request: FeedbackRequest):
    """记录用户反馈评分（thumbs up/down）到 Langfuse"""
    from src.observability import record_score

    trace_id = request.trace_id or ""
    ok = record_score(
        trace_id=trace_id,
        name=request.name,
        value=request.score,
        comment=request.comment,
    )
    return {
        "success": ok,
        "message": "Feedback recorded" if ok else "Langfuse not available, feedback not persisted",
    }


# --- Admin routes ---


@app.get("/admin")
async def admin_page():
    return _static_page(
        "static",
        "admin.html",
        cache_control="no-store, private",
    )


@app.get("/api/admin/access-status")
async def admin_access_status(req: Request):
    username = _require_admin(req)
    return {"success": True, "is_admin": True, "username": username}


@app.get("/api/admin/overview")
async def admin_overview():
    """管理后台概览数据"""
    from src.admin import get_ai_metrics, _check_langfuse
    from src.progress_db import list_all_students

    metrics = get_ai_metrics()
    return {
        "sessions": metrics["sessions"],
        "total_students": len(list_all_students(limit=10000)),
        "langfuse_enabled": _check_langfuse(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/admin/marketing-summary")
async def admin_marketing_summary(req: Request, days: int = 180):
    _require_admin(req)
    return await run_blocking(
        marketing_summary,
        days,
        timeout=10,
        limit_concurrency=False,
    )


@app.get("/api/admin/users")
async def admin_list_users(limit: int = 100, offset: int = 0):
    """列出所有学生"""
    from src.progress_db import list_all_students
    users = list_all_students(limit=limit, offset=offset)
    return {"success": True, "users": users}


@app.post("/api/admin/users")
async def admin_create_user(request: AdminUserCreateRequest):
    """管理员创建新学生"""
    from src.progress_db import create_student
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if not (1 <= request.year_group <= 6):
        raise HTTPException(status_code=400, detail="Year group must be 1-6")
    if not (5 <= request.age <= 11):
        raise HTTPException(status_code=400, detail="Age must be 5-11")
    student = create_student(
        name=request.name.strip(),
        year_group=request.year_group,
        age=request.age,
    )
    return {"success": True, "student": student}


@app.get("/api/admin/users/{student_id}")
async def admin_get_user(student_id: str):
    """获取学生详细信息"""
    from src.progress_db import get_student_detail
    detail = get_student_detail(student_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True, "student": detail}


@app.put("/api/admin/users/{student_id}")
async def admin_update_user(student_id: str, request: AdminUserUpdateRequest):
    """更新学生信息"""
    from src.progress_db import update_student
    updates = request.model_dump(exclude_unset=True)
    if request.is_active is not None:
        updates["is_active"] = 1 if request.is_active else 0
    ok = update_student(student_id, **updates)
    return {"success": ok}


@app.delete("/api/admin/users/{student_id}")
async def admin_delete_user(student_id: str):
    """删除学生及所有相关数据（UK GDPR 被遗忘权）"""
    from src.progress_db import delete_student
    ok = delete_student(student_id)
    return {"success": ok, "message": "Student and all related data deleted (GDPR erasure)"}


@app.get("/api/admin/subscriptions")
async def admin_subscriptions(refresh: bool = True):
    """Return the subscription overview after an optional Stripe repair pass."""
    stripe_sync: Dict[str, Any] = {
        "attempted": False,
        "succeeded": True,
    }
    if refresh:
        from src.webapp.billing import refresh_stripe_subscription_catalog
        try:
            stripe_sync = await run_blocking(
                refresh_stripe_subscription_catalog,
                100,
                timeout=15,
                limit_concurrency=False,
            )
        except Exception:
            stripe_sync = {
                "attempted": True,
                "succeeded": False,
            }
            logger.exception(
                "Admin subscription refresh could not reconcile Stripe"
            )
    from src.admin import get_subscription_overview
    overview = await run_blocking(
        get_subscription_overview,
        timeout=10,
        limit_concurrency=False,
    )
    return {**overview, "stripe_sync": stripe_sync}


@app.post("/api/admin/subscriptions")
async def admin_create_subscription(request: AdminSubscriptionCreateRequest):
    """Developer-only manual subscription helper."""
    if not _dev_mode:
        raise HTTPException(status_code=410, detail="Manual subscriptions are disabled. Use Stripe Checkout and verified webhooks.")
    from src.admin import create_admin_subscription
    if not request.email or not request.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if request.duration not in ("5_days", "30_days"):
        raise HTTPException(status_code=400, detail="Duration must be '5_days' or '30_days'")
    try:
        result = create_admin_subscription(
            email=request.email.strip(),
            name=request.name.strip(),
            duration=request.duration,
        )
        return {"success": True, "subscription": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[Admin] 创建订阅失败: %s", e)
        raise HTTPException(status_code=500, detail="The administrator action failed.")


# --- Test account management for admins ---

@app.post("/api/admin/test-account")
async def admin_create_test_account(req: Request):
    """Create a persistent test user (admin-only). Request JSON: {username, password, create_subscription: bool}

    The created user will be marked as a test account which bypasses subscription checks.
    In dev mode an accompanying local subscription can also be created.
    """
    data = await req.json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    create_sub = bool(data.get("create_subscription", True))
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    from src.progress_db import create_user, set_user_test_flag, create_local_subscription
    try:
        create_user(username, password)
    except ValueError:
        raise HTTPException(status_code=400, detail="User already exists")
    # mark as test
    set_user_test_flag(username, True)

    # Optionally create a long-lived local subscription in dev mode
    if _dev_mode and create_sub:
        try:
            create_local_subscription(customer_email=username, customer_name=username,
                                      product_name="Admin Test Account", duration_days=365)
        except Exception:
            logger.warning("Failed to create local subscription for test account %s", username)

    return {"success": True, "username": username}


@app.post("/api/admin/users/{username}/test-toggle")
async def admin_toggle_test(username: str, enable: bool = True):
    """Toggle a persistent user's test status (enable=true/false)."""
    from src.progress_db import get_user_by_username, set_user_test_flag
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ok = set_user_test_flag(username, bool(enable))
    return {"success": ok, "is_test": bool(enable)}


@app.get("/api/admin/ai-metrics")
async def admin_ai_metrics():
    """获取 AI 系统运行指标"""
    from src.admin import get_ai_metrics
    return get_ai_metrics()


@app.get("/api/admin/ai-evaluation")
async def admin_ai_evaluation():
    """获取 AI 质量评估汇总"""
    from src.admin import get_evaluation_summary
    return get_evaluation_summary()


@app.post("/api/admin/cache/clear")
async def admin_clear_cache():
    """清空所有缓存"""
    from src.admin import clear_all_caches
    cleared = clear_all_caches()
    return {"success": True, "cleared": cleared}


@app.get("/api/admin/dev-mode-status")
async def admin_dev_mode_status():
    """Returns whether the application is running in development mode."""
    return {"is_dev_mode": _dev_mode}


# ---- AI 监控 API ----

@app.get("/api/admin/ai-monitor/stats")
async def admin_ai_monitor_stats(hours: int = 24):
    """获取 AI 系统统计信息"""
    from src.ai_monitor import get_ai_stats
    return get_ai_stats(hours=hours)


@app.get("/api/admin/ai-monitor/requests")
async def admin_ai_monitor_requests(
        limit: int = 100,
        offset: int = 0,
        provider: str = None,
        model: str = None,
        status: str = None,
        student_id: str = None,
        subject: str = None,
        operation: str = None,
):
    """获取 LLM 请求记录（支持筛选）"""
    from src.ai_monitor import get_requests_by_filter
    return get_requests_by_filter(
        provider=provider,
        model=model,
        status=status,
        student_id=student_id,
        subject=subject,
        operation=operation,
        limit=limit,
    )


@app.get("/api/admin/ai-monitor/request/{request_id}")
async def admin_ai_monitor_request_detail(request_id: str):
    """获取单个请求的详细信息"""
    from src.ai_monitor import get_request_detail
    detail = get_request_detail(request_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Request not found")
    return detail


@app.get("/api/admin/ai-monitor/models")
async def admin_ai_monitor_models():
    """获取模型对比数据"""
    from src.ai_monitor import get_model_comparison
    return get_model_comparison()


@app.get("/api/admin/ai-monitor/conversations")
async def admin_ai_monitor_conversations(student_id: str = None, limit: int = 50):
    """获取对话历史"""
    from src.ai_monitor import get_conversations
    return get_conversations(student_id=student_id, limit=limit)


# --- Admin endpoints: embedding cache & auth-user management ---

@app.get("/api/admin/auth-users")
async def admin_auth_users(limit: int = 100, offset: int = 0):
    """List registered auth users (username, created_at, is_test)"""
    from src.progress_db import list_all_users
    users = list_all_users(limit=limit, offset=offset)
    return {"success": True, "users": users}


@app.post("/api/admin/broadcast-message")
async def admin_broadcast_message(req: Request):
    """管理员向选中的用户发送消息（同时显示在用户消息箱和发送邮件通知）"""
    _require_admin(req)
    try:
        data = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    usernames = data.get("usernames", [])
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()

    if not isinstance(usernames, list) or len(usernames) == 0:
        raise HTTPException(status_code=400, detail="Please select at least one user.")
    if len(subject) < 2:
        raise HTTPException(status_code=400, detail="Please enter a subject (at least 2 characters).")
    if len(message) < 2:
        raise HTTPException(status_code=400, detail="Please enter a message (at least 2 characters).")

    from src.webapp.message_store import MessageStore
    from src.webapp.email_service import send_admin_broadcast_email

    store = MessageStore(project_root)
    results = []

    for username in usernames:
        username = username.strip().lower()
        if not username:
            continue

        owner_id = f"account:{username}"
        try:
            # 在用户消息箱中创建消息
            msg_item, _token = await asyncio.to_thread(
                store.create_message,
                owner_id=owner_id,
                contact_email=username,
                category="general",
                subject=subject,
                message=message,
            )
            # 发送邮件通知
            email_status, email_error = await asyncio.to_thread(
                send_admin_broadcast_email,
                to_email=username,
                subject=subject,
                message=message,
            )
            results.append({
                "username": username,
                "message_id": msg_item["id"],
                "email_status": email_status,
                "email_error": email_error,
            })
        except Exception as e:
            results.append({
                "username": username,
                "error": str(e),
            })

    return {"success": True, "results": results}


@app.get("/api/admin/embedding-cache/stats")
async def admin_embedding_cache_stats():
    from src.embedding_cache import get_stats
    try:
        return {"success": True, "stats": get_stats()}
    except Exception as e:
        logger.error("[Admin] embedding cache stats error: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": "The administrator request failed."})


@app.post("/api/admin/embedding-cache/cleanup")
async def admin_embedding_cache_cleanup(req: Request):
    """Cleanup the embedding cache.
    JSON body: { days: optional int, max_rows: optional int }
    """
    try:
        data = await req.json()
    except Exception:
        data = {}
    days = data.get('days')
    max_rows = data.get('max_rows')
    from src.embedding_cache import cleanup_older_than, ensure_max_rows
    result = {}
    try:
        if days:
            removed = cleanup_older_than(int(days))
            result['removed'] = removed
        if max_rows:
            trimmed = ensure_max_rows(int(max_rows))
            result['trimmed'] = trimmed
        return {"success": True, "result": result}
    except Exception as e:
        logger.error("[Admin] embedding cache cleanup failed: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": "The administrator request failed."})


static_path = os.path.join(project_root, "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


def main():
    print(
        """
===============================================================
                    Homework Magic
             AI Tutor for UK Primary Schools
                  (FastAPI + Uvicorn)
===============================================================
    """
    )

    initialize()

    import uvicorn

    port = int(os.environ.get("PORT", 5000))
    print(
        f"""
Starting server...
Homepage:         http://localhost:{port}
Main App:         http://localhost:{port}/app

Available pages:
  - http://localhost:{port}/
  - http://localhost:{port}/ks1-homework
  - http://localhost:{port}/ks2-homework
  - http://localhost:{port}/elevenplus-practice
  - http://localhost:{port}/elevenplus-mock-exams
  - http://localhost:{port}/check-my-homework
  - http://localhost:{port}/app

Press Ctrl+C to stop
    """
    )

    uvicorn.run(
        "web_app:app", host="0.0.0.0", port=port, reload=_dev_mode,
        workers=1 if _dev_mode else int(os.getenv("WEB_CONCURRENCY", "1")),
        proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes"),
    )


# ===== VOICE FEATURE ENDPOINTS (Tier 0: Browser-native) =====

@app.post("/api/log-voice-usage")
async def log_voice_usage(request: Request):
    """Increment an aggregate voice-feature counter.
    
    POST body: {
        event_type: 'tts_used' | 'stt_used',
        year_group: int (1-6),
        subject: str
    }

    Account, learner, cookie, IP and free-text values are not retained by the
    application metric. No RAG, embedding or AI call is made.
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.warning("[Voice] Failed to parse JSON: %s", e)
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    event_type = data.get("event_type")
    year_group = data.get("year_group")
    subject = data.get("subject")

    if event_type not in ("tts_used", "stt_used") or year_group is None or not subject:
        return JSONResponse(
            {"success": False, "error": "Missing or invalid fields"},
            status_code=400
        )

    try:
        await run_blocking(
            record_voice_event,
            event_type,
            year_group=int(year_group),
            subject=str(subject),
            timeout=5,
            limit_concurrency=False,
        )
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error("[Voice] Failed to log event: %s", e)
        return JSONResponse(
            {"success": False, "error": "Failed to log event"},
            status_code=500
        )


@app.get("/api/admin/voice-usage-stats")
async def voice_usage_stats(request: Request):
    """Get aggregated voice feature usage stats by age and subject.
    
    Access: admin/dev-mode only (gate via existing auth checks if applicable)
    """
    _require_admin(request)
    try:
        stats = await run_blocking(
            voice_summary,
            180,
            timeout=10,
            limit_concurrency=False,
        )
        return JSONResponse({"success": True, "stats": stats})
    except Exception as e:
        logger.error("[Voice] Failed to fetch stats: %s", e)
        return JSONResponse(
            {"success": False, "error": "Failed to fetch stats"},
            status_code=500
        )


if __name__ == "__main__":
    main()
