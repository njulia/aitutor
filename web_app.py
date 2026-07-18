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
import base64
import re  # Ensure re is imported for regex operations
import json # Added: Import the json module
import html
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, status  # Added Request and status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image
from src.progress_db import set_user_test_flag, is_user_test, get_user_by_username

from src.webapp.runtime import (
    configure_cors, install_hardening, owner_key, run_blocking,
    production_configuration_issues, validate_production_configuration,
)
from src.webapp.session_store import TutorSessionStore
from src.webapp.upload_utils import stream_upload_to_temp
from src.webapp.message_routes import create_message_router
from src.webapp.account_routes import build_account_router
from src.webapp.memory_routes import build_memory_router
from src.webapp.password_reset_routes import create_password_reset_router
from src.webapp.billing import build_billing_router
from src.webapp.question_utils import (
    _split_homework_into_questions as split_public_homework,
    parse_public_questions,
    public_homework_content,
)
from src.webapp.review_service import (
    review_homework as service_review_homework,
    explain_deep as service_explain_deep,
    improve_practice as service_improve_practice,
)
from src.webapp.upload_utils import decode_base64_image_to_temp
from src.webapp.child_safety import detect_safeguarding_concern


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


def user_has_subscription(req: Optional[Request] = None, student_id: Optional[str] = None, username: Optional[str] = None) -> bool:
    """Read access from the local account database synchronised by Stripe webhooks.

    No network call is made on the request path. This lowers latency and avoids
    granting or denying access because Stripe is temporarily unavailable.
    """
    if req and (student_id is None or username is None):
        resolved_student_id, resolved_username, _ = _get_user_or_anonymous_id(req)
        student_id = student_id or resolved_student_id
        username = username or resolved_username
    if not username or (student_id and str(student_id).startswith("anon_")):
        return False
    try:
        if is_user_test(username):
            return True
        from src.webapp.account_store import account_has_active_subscription

        if account_has_active_subscription(username):
            return True
        # Backward-compatible local developer subscriptions only. Production
        # access must come from verified Stripe webhook state.
        if _dev_mode:
            from src.progress_db import get_local_subscriptions_by_email
            return any(item.get("status") == "active" for item in get_local_subscriptions_by_email(username))
        return False
    except Exception:
        logger.exception("Subscription lookup failed")
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

    try:
        os.remove(file_path)
    except OSError:
        pass

    return content, is_image


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


def _get_user_or_anonymous_id(req: Request) -> tuple[str, Optional[str], Optional[str]]:
    """
    Determines the student_id and username for the current request.
    Returns (student_id, username_if_logged_in, new_anonymous_session_id_to_set_in_cookie).
    new_anonymous_session_id_to_set_in_cookie will be None if no new cookie is needed.
    """
    from src.auth_tokens import verify_token  # Moved to top-level import
    # 1. Check for logged-in user
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

    # 2. Check for anonymous session ID cookie
    anonymous_session_id = req.cookies.get("anon_session_id")
    if anonymous_session_id:
        return anonymous_session_id, None, None # No username for anonymous

    # 3. Generate a new anonymous session ID
    new_anon_session_id = f"anon_{uuid.uuid4().hex}" # Prefix to distinguish from real student_ids
    return new_anon_session_id, None, new_anon_session_id


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


def generate_homework_with_profile(profile: dict, subjects: list, is_eleven_plus: bool = False):
    """为多个科目生成作业（并行执行以降低延迟）"""
    from src.homework_generator import generate_homework_parallel

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 3)}_default"

    return generate_homework_parallel(profile, subjects, llm, is_eleven_plus=is_eleven_plus)


# Use the maintained, token-budgeted review service.  These wrappers keep the
# public module API stable for tests and existing integrations.
def review_homework(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile=None,
    *,
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

def _static_page(*parts: str) -> FileResponse:
    path = os.path.join(project_root, *parts)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Page not found")
    # 禁用缓存，确保开发时总是获取最新文件
    return FileResponse(path, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })


class ProfileRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    subjects: list = Field(default_factory=list)
    quick_select: bool = False
    year: Optional[int] = None
    student_id: Optional[str] = None
    is_eleven_plus: bool = False
    mode: Optional[str] = "homework"  # Added mode field


class ReviewRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    session_id: Optional[str] = None
    is_tutor_mode: Optional[bool] = False  # Added for tutor mode review
    from_rag: Optional[bool] = False  # Whether the question came from RAG (free)
    homework_doc_id: Optional[str] = None  # RAG document id if available
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
async def index():
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


@app.get("/check-my-homework")
async def check_homework():
    return _static_page("static", "check-my-homework.html")


@app.get("/register")
async def register_page():
    return _static_page("static", "register.html")


@app.get("/login")
async def login_page():
    return _static_page("static", "login.html")


@app.get("/pricing")
async def login_page():
    return _static_page("static", "pricing.html")


@app.get("/privacy")
async def privacy_page():
    path = os.path.join(project_root, "static", "privacy.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Page not found")
    content = open(path, encoding="utf-8").read()
    replacements = {
        "{{DATA_CONTROLLER_NAME}}": os.getenv("DATA_CONTROLLER_NAME", "[Add the legal operator name before launch]"),
        "{{PRIVACY_CONTACT_EMAIL}}": os.getenv("PRIVACY_CONTACT_EMAIL", "[Add a privacy contact email before launch]"),
        "{{PRIVACY_POSTAL_ADDRESS}}": os.getenv("PRIVACY_POSTAL_ADDRESS", "[Add a postal contact address before launch]"),
    }
    for marker, value in replacements.items():
        content = content.replace(marker, html.escape(str(value), quote=True))
    return HTMLResponse(content, headers={"Cache-Control": "public, max-age=300"})


@app.get("/safety")
async def safety_page():
    return _static_page("static", "safety.html")


@app.get("/progress")
async def progress_page():
    return _static_page("static", "progress.html")


@app.get("/app")
async def app_page():
    return _static_page("static", "app.html")


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
    seo_sitemap = os.path.join(project_root, "static", "--seo", "sitemap.xml")
    if os.path.isfile(seo_sitemap):
        return FileResponse(seo_sitemap, media_type="application/xml")
    raise HTTPException(status_code=404, detail="Sitemap not found")


@app.get("/elevenplus/articles")
async def elevenplus_articles():
    return _static_page("static", "elevenplus", "articles.html")


@app.get("/elevenplus/uk-grammar-guide")
async def elevenplus_grammar_guide():
    return _static_page("static", "elevenplus", "uk_grammar_guide.html")


@app.get("/elevenplus/11plus-vocabulary-list")
async def elevenplus_vocabulary_list():
    return _static_page("static", "elevenplus", "11plus_vocabulary_list.html")


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
    resolved_id, _username, new_anon_id = _get_user_or_anonymous_id(request)
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
    """Canonicalise public subject labels without changing ordinary 11+ requests."""
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


@app.post("/api/generate")
async def api_generate(req: Request, request: ProfileRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        request.student_id = resolved_student_id
        request.profile = dict(request.profile or {})
        request.profile["student_id"] = resolved_student_id
        description_for_safety = str(request.profile.get("description") or "").strip()
        concern = detect_safeguarding_concern(description_for_safety)
        if concern is not None:
            return JSONResponse(content={
                "success": False,
                "error": concern.message,
                "safety_intervention": True,
                "safety_category": concern.category,
            })
        profile = resolve_profile(
            request.profile,
            quick_select=request.quick_select,
            year=request.year,
            student_id=resolved_student_id,
        )

        subjects = list(request.subjects or [])
        if not subjects:
            description = str(request.profile.get("description") or profile.get("description") or "").strip()
            if description:
                from src.ui.shared import parse_profile_from_natural_language

                parsed = await run_blocking(
                    parse_profile_from_natural_language,
                    description,
                    llm,
                    timeout=20,
                )
                if parsed:
                    profile.update(parsed)
                    profile["student_id"] = resolved_student_id
                    subjects = list(parsed.get("extracted_subjects") or [])
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
            return JSONResponse(status_code=400, content={"success": False, "error": "Please choose a subject."})

        generated = await run_blocking(
            generate_homework_with_profile,
            profile,
            subjects,
            request.is_eleven_plus,
            timeout=120,
        )
        all_homework_results = _public_homework_results(generated, is_eleven_plus=request.is_eleven_plus)

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
                    question["plan_week"] = hw_block.get("plan_week") or profile.get("plan_week")
                    question["content_type"] = hw_block.get("content_type")
                individual_questions.extend(split_questions)

            has_sub = await run_blocking(
                user_has_subscription,
                req,
                resolved_student_id,
                logged_in_username,
                timeout=12,
                limit_concurrency=False,
            )
            if not has_sub:
                rag_only = [item for item in individual_questions if item.get("from_rag")]
                if rag_only:
                    response = JSONResponse({
                        "success": True,
                        "homework": rag_only,
                        "profile": profile,
                        "mode": "tutor",
                        "note": "Library questions are available. A subscription is needed for newly generated tutor questions.",
                    })
                    _set_anon_cookie(response, new_anon_session_id, req)
                    return response
                status_code = 401 if logged_in_username is None else 402
                message = (
                    "A parent or guardian needs to sign in for this tutor feature."
                    if status_code == 401
                    else "This tutor feature needs an active subscription."
                )
                return JSONResponse(status_code=status_code, content={"success": False, "error": message})

            response = JSONResponse({
                "success": True,
                "homework": individual_questions,
                "profile": profile,
                "mode": "tutor",
            })
            _set_anon_cookie(response, new_anon_session_id, req)
            return response

        response = JSONResponse({
            "success": True,
            "homework": all_homework_results,
            "profile": profile,
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
async def api_review(req: Request, request_body: ReviewRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)
        profile = dict(request_body.profile or {})
        profile["student_id"] = resolved_student_id

        if request_body.is_tutor_mode and not request_body.from_rag:
            has_sub = await run_blocking(
                user_has_subscription,
                req,
                resolved_student_id,
                logged_in_username,
                timeout=12,
                limit_concurrency=False,
            )
            if not has_sub:
                status_code = 401 if logged_in_username is None else 402
                message = (
                    "A parent or guardian needs to sign in for this tutor check."
                    if status_code == 401
                    else "This tutor check needs an active subscription."
                )
                return JSONResponse(status_code=status_code, content={"success": False, "error": message})

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

        result = await run_blocking(
            review_homework,
            request_body.homework,
            request_body.answers,
            request_body.subject,
            profile,
            is_tutor_mode=bool(request_body.is_tutor_mode),
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
        logger.exception("Homework review failed")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not check the answers just now. Please try again."},
        )


@app.post("/api/explain-deep")
async def api_explain_deep(req: Request, request_body: ExplainDeepRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        # Trusted library questions already have an answer key, so their detailed
        # explanation can be produced locally without charging for another model call.
        if not request_body.from_rag:
            has_sub = await run_blocking(
                user_has_subscription,
                req,
                resolved_student_id,
                logged_in_username,
                timeout=12,
                limit_concurrency=False,
            )
            if not has_sub:
                status_code = 401 if logged_in_username is None else 402
                message = (
                    "A parent or guardian needs to sign in for detailed explanations."
                    if status_code == 401
                    else "Detailed explanations need an active subscription."
                )
                return JSONResponse(status_code=status_code, content={"success": False, "error": message})

        profile = dict(request_body.profile or {})
        profile["student_id"] = resolved_student_id
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
        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)
        has_sub = await run_blocking(
            user_has_subscription,
            req,
            resolved_student_id,
            logged_in_username,
            timeout=12,
            limit_concurrency=False,
        )
        if not has_sub:
            status_code = 401 if logged_in_username is None else 402
            message = (
                "A parent or guardian needs to sign in for extra practice."
                if status_code == 401
                else "Extra practice needs an active subscription."
            )
            return JSONResponse(status_code=status_code, content={"success": False, "error": message})

        profile = dict(request_body.profile or {})
        profile["student_id"] = resolved_student_id
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
        response = JSONResponse(content=result)
        _set_anon_cookie(response, new_anon_session_id, req)
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Practice generation failed")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not make extra practice just now. Please try again."},
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
        resolved_student_id, logged_in_username, _ = _get_user_or_anonymous_id(req)

        if logged_in_username is None:
            return JSONResponse(status_code=401, content={"success": False, "error": "Login required to view progress."})

        target_student_id = str(student_id or resolved_student_id).strip()
        if not target_student_id:
            return JSONResponse(status_code=400, content={"success": False, "error": "A learner profile is required."})

        # A parent/guardian may view only learner profiles belonging to their account.
        from src.webapp.account_store import ensure_account, student_belongs_to_account
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


def _request_session_owner(request: Request) -> tuple[str, Optional[str]]:
    resolved_id, username, new_anon_id = _get_user_or_anonymous_id(request)
    return owner_key(username or resolved_id), new_anon_id


@app.post("/api/sessions")
async def create_session(request: Request):
    session_owner, new_anon_id = _request_session_owner(request)
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
    session_owner, _ = _request_session_owner(request)
    session = await asyncio.to_thread(tutor_session_store.get, session_id, session_owner)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.put("/api/sessions/{session_id}")
async def update_session(request: Request, session_id: str, body: SessionUpdateRequest):
    session_owner, _ = _request_session_owner(request)
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
    session_owner, _ = _request_session_owner(request)
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
async def check_subscription_api(req: Request):
    resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)
    has_sub = await run_blocking(
        user_has_subscription,
        req,
        resolved_student_id,
        logged_in_username,
        timeout=12,
        limit_concurrency=False,
    )
    response = JSONResponse({
        "has_subscription": bool(has_sub),
        "logged_in": logged_in_username is not None,
    })
    _set_anon_cookie(response, new_anon_session_id, req)
    return response


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
async def api_register(request_body: AuthRequest, req: Request):
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
        response = JSONResponse({"success": True})
        response.set_cookie(
            "session", token, httponly=True, samesite="lax",
            secure=_cookie_should_be_secure(req), path="/", max_age=12 * 60 * 60,
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
        content, is_image = await asyncio.to_thread(process_uploaded_file, filepath)
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
    return _static_page("static", "admin.html")


@app.get("/api/admin/access-status")
async def admin_access_status(req: Request):
    username = _require_admin(req)
    return {"success": True, "is_admin": True, "username": username}


@app.get("/api/admin/overview")
async def admin_overview():
    """管理后台概览数据"""
    from src.admin import get_ai_metrics, get_subscription_overview, _check_langfuse
    from src.progress_db import list_all_students, get_all_sessions_summary

    metrics = get_ai_metrics()
    students = list_all_students(limit=1)  # 只取数量
    return {
        "sessions": metrics["sessions"],
        "total_students": len(list_all_students(limit=10000)),
        "langfuse_enabled": _check_langfuse(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


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
async def admin_subscriptions():
    """获取订阅概览"""
    from src.admin import get_subscription_overview
    return get_subscription_overview()


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


if __name__ == "__main__":
    main()