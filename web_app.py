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
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, status  # Added Request and status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image
from src.progress_db import set_user_test_flag, is_user_test, get_user_by_username

from src.webapp.runtime import (
    configure_cors, install_hardening, owner_key, public_error, run_blocking,
    validate_database_configuration, settings as runtime_settings,
)
from src.webapp.session_store import TutorSessionStore
from src.webapp.upload_utils import stream_upload_to_temp
from src.webapp.review_service import (
    review_homework as review_homework_service,
    explain_deep as explain_deep_service,
    improve_practice as improve_practice_service,
)
from src.webapp.account_store import (
    account_has_active_subscription, ensure_account, ensure_default_student,
    student_belongs_to_account,
)
from src.webapp.account_routes import build_account_router
from src.webapp.message_routes import create_message_router
from src.webapp.password_reset_routes import create_password_reset_router
from src.webapp.memory_routes import build_memory_router
from src.webapp.billing import build_billing_router
from src.webapp.question_utils import (
    _split_homework_into_questions,
    parse_public_questions,
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


def _token_from_request(req: Request) -> Optional[str]:
    """Read only opaque authentication tokens, never a user-controlled ID."""
    return req.cookies.get("session") or req.headers.get("Authorization")


def _resolve_username(req: Request) -> Optional[str]:
    token = _token_from_request(req)
    if not token:
        return None
    try:
        from src.auth_tokens import verify_token

        username = verify_token(token)
        if username and get_user_by_username(username):
            return str(username).strip().lower()
    except Exception:
        logger.exception("Authentication token validation failed")
    return None


def _require_admin(req: Request) -> str:
    username = _resolve_username(req)
    if not username:
        raise HTTPException(status_code=403, detail="Admin access denied")
    allowlist = {
        item.strip().lower()
        for item in os.getenv("ADMIN_EMAILS", "").split(",")
        if item.strip()
    }
    if username not in allowlist:
        raise HTTPException(status_code=403, detail="Admin access denied")
    return username

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
    """Validate production storage and initialise lightweight shared services."""
    validate_database_configuration()
    await run_blocking(tutor_session_store.initialise, limit_concurrency=False)
    initialize()
    yield


def is_logged_in(req: Request) -> bool:
    return _resolve_username(req) is not None


def user_has_subscription(
    req: Optional[Request] = None,
    student_id: Optional[str] = None,
    username: Optional[str] = None,
    required_plans: Optional[List[str]] = None,
) -> bool:
    """Check the local account entitlement table; never call Stripe per request."""
    username = username or (_resolve_username(req) if req else None)
    if not username:
        return False
    try:
        if is_user_test(username):
            return True
        if account_has_active_subscription(username, required_plans=required_plans):
            return True
        if _dev_mode:
            from src.progress_db import get_local_subscriptions_by_email

            subs = get_local_subscriptions_by_email(username)
            active_subs = [item for item in subs if item.get("status") == "active"]
            if not active_subs:
                return False
            if required_plans:
                # In dev mode, we also respect the family_monthly super-set
                effective_required = set(required_plans)
                return any(
                    item.get("plan") == "family_monthly" or item.get("plan") in effective_required
                    for item in active_subs
                )
            return True
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
    """Decode a browser image data URL with strict type and size checks."""
    import binascii
    import tempfile

    match = re.fullmatch(
        r"data:image/(png|jpeg|jpg|gif|heic);base64,([A-Za-z0-9+/=\r\n]+)",
        (data_url or "").strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError("Please upload a supported image file.")

    image_type = match.group(1).lower()
    encoded = re.sub(r"\s+", "", match.group(2))
    estimated_size = (len(encoded) * 3) // 4
    if estimated_size > MAX_UPLOAD_BYTES:
        raise ValueError("Image is too large (maximum 16 MB).")

    try:
        image_data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The image data is not valid.") from exc
    if not image_data or len(image_data) > MAX_UPLOAD_BYTES:
        raise ValueError("Image is empty or too large.")

    suffix = ".jpg" if image_type in {"jpg", "jpeg"} else f".{image_type}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_data)
        tmp_path = tmp.name

    try:
        return extract_text_from_image(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
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
    """Resolve a pseudonymous learner ID and the parent account email, if any."""
    username = _resolve_username(req)
    if username:
        try:
            account = ensure_account(username)
            learner = ensure_default_student(account["id"])
            return str(learner["id"]), username, None
        except Exception:
            logger.exception("Could not resolve the default learner profile")
            return owner_key(username), username, None

    anonymous_session_id = (req.cookies.get("anon_session_id") or "").strip()
    if re.fullmatch(r"anon_[a-f0-9]{32}", anonymous_session_id):
        return anonymous_session_id, None, None

    new_anon_session_id = f"anon_{uuid.uuid4().hex}"
    return new_anon_session_id, None, new_anon_session_id


def _set_anon_cookie(response: JSONResponse, value: Optional[str]) -> None:
    if value:
        response.set_cookie(
            "anon_session_id", value, httponly=True, samesite="lax",
            secure=not _dev_mode, max_age=365 * 24 * 60 * 60,
        )


def _request_session_owner(request: Request) -> tuple[str, Optional[str]]:
    learner_id, username, new_anon_id = _get_user_or_anonymous_id(request)
    return owner_key(username or learner_id), new_anon_id


def generate_homework_with_profile(profile: dict, subjects: list, is_eleven_plus: bool = False):
    """为多个科目生成作业（并行执行以降低延迟）"""
    from src.homework_generator import generate_homework_parallel

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 3)}_default"

    return generate_homework_parallel(profile, subjects, llm, is_eleven_plus=is_eleven_plus)


def _parse_student_answers_to_map(student_answers_text: str, target_subject: str, rag_questions: List[str]) -> Dict[
    str, str]:
    """
    Heuristically parses student answers to map them to known RAG questions for a specific subject.
    Assumes student_answers_text might contain multiple subjects delimited by '--- Subject ---'.
    This is a best-effort approach due to unstructured student input.
    """
    answer_map = {}

    # 1. Extract the block of answers for the target_subject
    subject_block = ""
    start_marker = f"--- {target_subject} ---"
    start_index = student_answers_text.find(start_marker)

    if start_index == -1:
        # If subject marker not found, assume the whole text is for the target subject
        # This is a fallback and might be wrong if multiple subjects are present without markers.
        subject_block = student_answers_text.strip()
    else:
        # Extract the content after the start marker
        content_after_marker = student_answers_text[start_index + len(start_marker):].strip()

        # Find the next subject marker
        next_subject_marker_match = re.search(r'--- [^-\n]+ ---', content_after_marker)
        if next_subject_marker_match:
            end_index = next_subject_marker_match.start()
            subject_block = content_after_marker[:end_index].strip()
        else:
            # No other subject markers, so the rest of the content is for the target subject
            subject_block = content_after_marker.strip()

    if not subject_block:
        return {}  # No answers found for this subject

    student_answer_lines = [line.strip() for line in subject_block.split('\n') if line.strip()]

    # Create a map from question number (e.g., "1") to full question text (e.g., "1. 4 x 3 = ?")
    # This is used for matching explicitly numbered student answers.
    rag_q_num_to_full_q_text = {}
    for q_text in rag_questions:
        num_match = re.match(r'^\s*(\d+)\.\s*', q_text)
        if num_match:
            rag_q_num_to_full_q_text[num_match.group(1)] = q_text

    # 2. Attempt to parse explicitly numbered student answers (e.g., "1. My answer")
    temp_answer_map_numbered = {}
    current_student_answer_parts = []
    current_student_q_num = None

    for line in student_answer_lines:
        num_match = re.match(r'^\s*(\d+)\.\s*(.*)', line)
        if num_match:
            if current_student_q_num is not None and current_student_answer_parts:
                if current_student_q_num in rag_q_num_to_full_q_text:
                    temp_answer_map_numbered[rag_q_num_to_full_q_text[current_student_q_num]] = " ".join(current_student_answer_parts)
            current_student_q_num = num_match.group(1)
            current_student_answer_parts = [num_match.group(2)]
        elif current_student_q_num is not None:
            current_student_answer_parts.append(line)
    
    if current_student_q_num is not None and current_student_answer_parts:
        if current_student_q_num in rag_q_num_to_full_q_text:
            temp_answer_map_numbered[rag_q_num_to_full_q_text[current_student_q_num]] = " ".join(current_student_answer_parts)

    if temp_answer_map_numbered:
        return temp_answer_map_numbered

    # 3. Fallback: If no numbered answers were found, try positional mapping
    # This handles cases where student just lists answers without numbering.
    # We map the first N student answer lines to the N RAG questions, where N is min(len(student_answer_lines), len(rag_questions))
    num_to_map = min(len(student_answer_lines), len(rag_questions))
    if num_to_map > 0:
        logger.debug(f"Positional mapping {num_to_map} student answers to RAG questions for subject {target_subject}.")
        for i in range(num_to_map):
            answer_map[rag_questions[i]] = student_answer_lines[i]
        return answer_map
    
    # 4. Fallback for single question (if only one RAG question and no other mapping)
    if not answer_map and len(rag_questions) == 1:
        answer_map[rag_questions[0]] = subject_block.strip()

    return answer_map


def review_homework(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile=None,
    is_tutor_mode: bool = False,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
):
    return review_homework_service(
        homework_content, student_answers, subject, profile,
        is_tutor_mode=is_tutor_mode, homework_doc_id=homework_doc_id,
        is_eleven_plus=is_eleven_plus, question_index=question_index,
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
    llm_client=None,
):
    return explain_deep_service(
        homework_content,
        student_answers,
        subject,
        profile,
        review_feedback,
        homework_doc_id=homework_doc_id,
        is_eleven_plus=is_eleven_plus,
        question_index=question_index,
        llm_client=llm_client or llm,
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
    llm_client=None,
):
    return improve_practice_service(
        homework_content,
        student_answers,
        subject,
        profile,
        review_feedback,
        homework_doc_id=homework_doc_id,
        is_eleven_plus=is_eleven_plus,
        question_index=question_index,
        llm_client=llm_client or llm,
    )

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
    question_index: Optional[int] = None
    is_eleven_plus: bool = False


class ExplainDeepRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    review_feedback: Optional[str] = None
    from_rag: bool = False
    homework_doc_id: Optional[str] = None
    question_index: Optional[int] = None
    is_eleven_plus: bool = False


class ImprovePracticeRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    review_feedback: Optional[str] = None
    from_rag: bool = False
    homework_doc_id: Optional[str] = None
    question_index: Optional[int] = None
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
    plan: Optional[str] = "homework_monthly"


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
    username: str = None
    email: str = None
    password: str

    def get_username(self) -> str:
        """Get username from either username or email field"""
        return (self.username or self.email or "").strip()


# Modular account, support, reset, memory and billing routes.
app.include_router(build_account_router(_resolve_username, _require_admin, tutor_session_store))
app.include_router(create_message_router(
    resolve_identity=_get_user_or_anonymous_id,
    require_admin=_require_admin,
    project_root=project_root,
))
app.include_router(create_password_reset_router(project_root=project_root, dev_mode=_dev_mode))
app.include_router(build_memory_router(_resolve_username))
app.include_router(build_billing_router(_resolve_username))

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
async def elevenplus_year_round_plan(req: Request):
    """Serve the dedicated 52-week 11+ study-plan page."""
    if not is_logged_in(req):
        return _static_page("static", "login.html")
    if not await run_blocking(user_has_subscription, req, required_plans=["elevenplus_monthly"], limit_concurrency=False):
        return _static_page("static", "pricing.html")
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


@app.get("/elevenplus/uk-11plus-vocabulary-list")
async def elevenplus_vocabulary_list():
    return _static_page("static", "elevenplus", "uk_11plus_vocabulary_list.html")


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
    return {"status": "ok", "initialized": initialized}


@app.get("/api/client-id")
async def get_client_id(request: Request):
    """Return the random cookie-backed anonymous ID; never expose or hash an IP."""
    learner_id, _username, new_anon_id = _get_user_or_anonymous_id(request)
    response = JSONResponse({"client_id": learner_id})
    _set_anon_cookie(response, new_anon_id)
    return response

@app.get("/api/subjects")
async def get_subjects():
    from src.models import (
        UK_PRIMARY_SUBJECTS,
        ELEVEN_PLUS_SUBJECTS,
        ELEVEN_PLUS_YEAR_ROUND_SUBJECTS,
    )

    return {
        "primary": UK_PRIMARY_SUBJECTS,
        "eleven_plus": ELEVEN_PLUS_SUBJECTS,
        "eleven_plus_year_round": ELEVEN_PLUS_YEAR_ROUND_SUBJECTS,
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


@app.post("/api/generate")
async def api_generate(req: Request, request: ProfileRequest):
    initialize()
    learner_id, username, new_anon_id = _get_user_or_anonymous_id(req)
    try:
        request.profile = dict(request.profile or {})
        request.profile["student_id"] = learner_id
        profile = resolve_profile(
            request.profile,
            quick_select=request.quick_select,
            year=request.year,
            student_id=learner_id,
        )

        from src.models import (
            UK_PRIMARY_SUBJECTS,
            ELEVEN_PLUS_SUBJECTS,
            ELEVEN_PLUS_YEAR_ROUND_SUBJECTS,
            canonical_year_round_subject,
            subject_display_name,
        )
        try:
            plan_week = int(profile.get("plan_week") or 0)
        except (TypeError, ValueError):
            plan_week = 0
        is_year_round_request = bool(request.is_eleven_plus and 1 <= plan_week <= 52)
        allowed = set(
            ELEVEN_PLUS_YEAR_ROUND_SUBJECTS
            if is_year_round_request
            else (ELEVEN_PLUS_SUBJECTS if request.is_eleven_plus else UK_PRIMARY_SUBJECTS)
        )

        # Check subscription for 11+ Premium features
        if request.is_eleven_plus:
            eleven_plus_sub = await run_blocking(
                user_has_subscription,
                req,
                learner_id,
                username,
                required_plans=["elevenplus_monthly"],
                limit_concurrency=False,
            )
            if not eleven_plus_sub:
                session_owner = owner_key(username or learner_id)
                pending = await run_blocking(
                    tutor_session_store.create,
                    session_owner,
                    {
                        "homework": [],
                        "profile": {"description": str(request.profile.get("description") or ""), "student_id": learner_id},
                        "mode": request.mode or "homework",
                        "is_eleven_plus": True,
                        "pending_access": True,
                    },
                    limit_concurrency=False,
                )
                return JSONResponse(
                    status_code=402,
                    content={
                        "success": False,
                        "error": "11+ Premium subscription required for this feature.",
                        "resume_session_id": pending["session_id"],
                    },
                )

        requested_subjects = []
        for raw_subject in request.subjects:
            subject = str(raw_subject).strip()
            if is_year_round_request:
                # Accept old pages that still send friendly names, but always
                # query/store with the new ``-1year`` RAG identifier.
                subject = canonical_year_round_subject(subject)
            if subject in allowed:
                requested_subjects.append(subject)
        subjects = list(dict.fromkeys(requested_subjects))[:4]

        if not subjects:
            description = str(request.profile.get("description") or "")[:2_000]
            # Most descriptions explicitly name a subject. Resolve that locally
            # before spending tokens on profile extraction.
            folded = description.casefold()
            subjects = [
                item for item in allowed
                if subject_display_name(item).casefold() in folded
            ][:4]
            year_match = re.search(r"\byear\s*([1-6])\b", folded)
            if year_match:
                profile["year_group"] = int(year_match.group(1))
                profile["age"] = profile["year_group"] + 4

            if not subjects and description:
                from src.ui.shared import parse_profile_from_natural_language
                parsed = await run_blocking(
                    parse_profile_from_natural_language,
                    description,
                    llm,
                    limit_concurrency=False,
                )
                if parsed:
                    profile.update({
                        key: value for key, value in parsed.items()
                        if key in {"year_group", "age", "key_stage", "english_level", "learning_goals", "weak_areas"}
                    })
                    parsed_subjects = parsed.get("extracted_subjects", [])
                    if is_year_round_request:
                        parsed_subjects = [canonical_year_round_subject(item) for item in parsed_subjects]
                    subjects = [item for item in parsed_subjects if item in allowed][:4]

        if not subjects:
            raise HTTPException(
                status_code=400,
                detail="Please choose a subject, such as Maths or English.",
            )

        all_homework = await run_blocking(
            generate_homework_with_profile,
            profile,
            subjects,
            request.is_eleven_plus,
            limit_concurrency=False,
        )
        for item in all_homework:
            item["is_eleven_plus"] = bool(request.is_eleven_plus)
            if not item.get("questions"):
                questions = parse_public_questions(str(item.get("content") or ""))
                if questions:
                    item["questions"] = questions

        mode = "tutor" if request.mode == "tutor" else "homework"
        if mode == "homework":
            response = JSONResponse({
                "success": True,
                "homework": all_homework,
                "profile": profile,
                "mode": mode,
            })
            _set_anon_cookie(response, new_anon_id)
            return response

        questions = []
        for block in all_homework:
            split = _split_homework_into_questions(block.get("content", ""), block.get("subject", ""))
            for index, question in enumerate(split):
                public_questions = question.get("questions") or parse_public_questions(
                    str(question.get("content") or "")
                )
                question.update({
                    "doc_id": block.get("doc_id"),
                    "from_rag": bool(block.get("from_rag")),
                    "question_index": index,
                    "is_eleven_plus": bool(request.is_eleven_plus),
                    "questions": public_questions,
                })
                if public_questions:
                    first_question = public_questions[0]
                    question["response_type"] = first_question.get("response_type", "text")
                    question["options"] = first_question.get("options", [])
                    question["question_text"] = first_question.get("question", "")
            questions.extend(split)

        has_subscription = await run_blocking(
            user_has_subscription,
            req,
            learner_id,
            username,
            limit_concurrency=False,
        )
        if has_subscription:
            response = JSONResponse({
                "success": True, "homework": questions, "profile": profile, "mode": mode
            })
            _set_anon_cookie(response, new_anon_id)
            return response

        rag_questions = [item for item in questions if item.get("from_rag")]
        non_rag_questions = [item for item in questions if not item.get("from_rag")]
        if rag_questions:
            response = JSONResponse({
                "success": True,
                "homework": rag_questions,
                "profile": profile,
                "mode": mode,
                "note": "Library questions are ready. Sign in and subscribe for AI-created tutor questions.",
            })
            _set_anon_cookie(response, new_anon_id)
            return response

        # Preserve already-created work in a short-lived, owner-bound server
        # session so login/payment does not make the learner start again.
        session_owner = owner_key(username or learner_id)
        pending = await run_blocking(
            tutor_session_store.create,
            session_owner,
            {
                "homework": non_rag_questions,
                "profile": profile,
                "mode": mode,
                "is_eleven_plus": bool(request.is_eleven_plus),
                "pending_access": True,
            },
            limit_concurrency=False,
        )
        status_code = 401 if username is None else 402
        response = JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": (
                    "A parent or guardian needs to sign in before this tutor session can continue."
                    if username is None
                    else "An active subscription is needed for AI-created tutor questions."
                ),
                "resume_session_id": pending["session_id"],
            },
        )
        _set_anon_cookie(response, new_anon_id)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        public_error(exc, "We could not make the homework just now. Please try again.")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not make the homework just now. Please try again."},
        )

@app.post("/api/review")
async def api_review(req: Request, request_body: ReviewRequest):
    initialize()
    learner_id, username, new_anon_id = _get_user_or_anonymous_id(req)
    profile = dict(request_body.profile or {})
    profile["student_id"] = learner_id

    if request_body.is_tutor_mode and not request_body.from_rag:
        has_subscription = await run_blocking(
            user_has_subscription, req, learner_id, username, limit_concurrency=False
        )
        if not has_subscription:
            raise HTTPException(
                status_code=401 if username is None else 402,
                detail=(
                    "A parent or guardian needs to sign in."
                    if username is None else "This feature needs an active subscription."
                ),
            )

    if request_body.session_id:
        session_owner = owner_key(username or learner_id)
        session = await run_blocking(
            tutor_session_store.get,
            request_body.session_id,
            session_owner,
            limit_concurrency=False,
        )
        if session:
            profile = {**session.get("profile", {}), **profile}

    try:
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
            limit_concurrency=False,
        )
        response = JSONResponse(result)
        _set_anon_cookie(response, new_anon_id)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        public_error(exc)
        return JSONResponse(status_code=500, content={"success": False, "error": "We could not check that answer just now."})

@app.post("/api/explain-deep")
async def api_explain_deep(req: Request, request_body: ExplainDeepRequest):
    initialize()
    learner_id, username, new_anon_id = _get_user_or_anonymous_id(req)
    # RAG-sourced explanations remain available without a paid model call gate;
    # AI-only explanations require the parent account entitlement.
    if not request_body.from_rag:
        has_subscription = await run_blocking(
            user_has_subscription, req, learner_id, username, limit_concurrency=False
        )
        if not has_subscription:
            raise HTTPException(
                status_code=401 if username is None else 402,
                detail="A parent or guardian needs to sign in." if username is None else "This feature needs an active subscription.",
            )
    try:
        profile = dict(request_body.profile or {})
        profile["student_id"] = learner_id
        result = await run_blocking(
            explain_deep,
            request_body.homework,
            request_body.answers,
            request_body.subject,
            profile,
            request_body.review_feedback or "",
            homework_doc_id=request_body.homework_doc_id,
            is_eleven_plus=request_body.is_eleven_plus,
            question_index=request_body.question_index,
            llm_client=llm,
            limit_concurrency=False,
            timeout=200,
        )
        response = JSONResponse(result)
        _set_anon_cookie(response, new_anon_id)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        public_error(exc)
        return JSONResponse(status_code=500, content={"success": False, "error": "We could not explain that homework just now."})

@app.post("/api/improve-practice")
async def api_improve_practice(req: Request, request_body: ImprovePracticeRequest):
    initialize()
    learner_id, username, new_anon_id = _get_user_or_anonymous_id(req)
    if not request_body.from_rag:
        has_subscription = await run_blocking(
            user_has_subscription, req, learner_id, username, limit_concurrency=False
        )
        if not has_subscription:
            raise HTTPException(
                status_code=401 if username is None else 402,
                detail="A parent or guardian needs to sign in." if username is None else "This feature needs an active subscription.",
            )
    try:
        profile = dict(request_body.profile or {})
        profile["student_id"] = learner_id
        result = await run_blocking(
            improve_practice,
            request_body.homework,
            request_body.answers,
            request_body.subject,
            profile,
            request_body.review_feedback or "",
            homework_doc_id=request_body.homework_doc_id,
            is_eleven_plus=request_body.is_eleven_plus,
            question_index=request_body.question_index,
            llm_client=llm,
            limit_concurrency=False,
            timeout=200,
        )
        response = JSONResponse(result)
        _set_anon_cookie(response, new_anon_id)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        public_error(exc)
        return JSONResponse(status_code=500, content={"success": False, "error": "We could not generate practice questions just now."})

@app.get("/api/progress/{student_id}")
async def api_get_progress(req: Request, student_id: str, subject: Optional[str] = None):
    username = _resolve_username(req)
    if not username:
        raise HTTPException(status_code=401, detail="A parent or guardian needs to sign in.")
    account = await run_blocking(ensure_account, username, limit_concurrency=False)
    belongs = await run_blocking(
        student_belongs_to_account, student_id, account["id"], limit_concurrency=False
    )
    if not belongs:
        raise HTTPException(status_code=404, detail="Learner profile not found.")
    if not await run_blocking(user_has_subscription, req, student_id, username, limit_concurrency=False):
        raise HTTPException(status_code=402, detail="Progress tracking needs an active subscription.")

    from src.progress_db import (
        get_progress_summary, get_score_history, get_topic_progress,
        get_daily_goal_stats, get_streak_info, get_accuracy_rate,
        generate_progress_feedback,
    )
    raw, scores, topics, daily, streak, accuracy = await asyncio.gather(
        run_blocking(get_progress_summary, student_id, limit_concurrency=False),
        run_blocking(get_score_history, student_id, subject, limit_concurrency=False),
        run_blocking(get_topic_progress, student_id, subject, limit_concurrency=False),
        run_blocking(get_daily_goal_stats, student_id, limit_concurrency=False),
        run_blocking(get_streak_info, student_id, limit_concurrency=False),
        run_blocking(get_accuracy_rate, student_id, limit_concurrency=False),
    )
    average = float(raw.get("average_accuracy", raw.get("average_score", 0)) or 0)
    by_subject = [
        {
            "subject": item.get("subject", ""),
            "avg_accuracy": float(item.get("avg_accuracy", item.get("avg_score", 0)) or 0),
            "total_sessions": int(item.get("count", 0) or 0),
        }
        for item in raw.get("subjects", [])
    ]
    score_history = []
    for item in scores:
        score = float(item.get("score", 0) or 0)
        max_score = float(item.get("max_score", 10) or 10)
        score_history.append({
            "subject": item.get("subject", ""),
            "score": score,
            "max_score": max_score,
            "created_at": item.get("created_at", ""),
        })
    feedback = generate_progress_feedback(
        total_sessions=int(raw.get("total_sessions", 0) or 0),
        avg_accuracy=average,
        current_streak=int(streak.get("current_streak", 0) or 0),
        daily_goal_rate=float(daily.get("daily_goal_rate", 0) or 0),
    )
    return {
        "success": True,
        "summary": {
            "overall": {"total_sessions": int(raw.get("total_sessions", 0) or 0), "avg_accuracy": average},
            "by_subject": by_subject,
        },
        "score_history": score_history,
        "topics": topics,
        "daily_goal": daily,
        "streak": streak,
        "accuracy_rate": accuracy,
        "feedback": feedback,
    }

@app.get("/api/quick-profile/{year}")
async def get_quick_profile(year: int):
    from src.models import SAMPLE_STUDENT_PROFILES

    student_id = f"student_{year}"
    profile = SAMPLE_STUDENT_PROFILES.get(
        student_id,
        {"year_group": year, "age": 5 + (year - 1), "student_id": student_id},
    )
    return {"success": True, "profile": profile}


@app.post("/api/sessions")
async def create_session(request: Request):
    session_owner, new_anon_id = _request_session_owner(request)
    session = await run_blocking(
        tutor_session_store.create,
        session_owner,
        {"homework": [], "profile": {}, "student_answers": "", "doc_id": "", "year_group": 3, "subject": "Maths"},
        limit_concurrency=False,
    )
    response = JSONResponse({"success": True, "session_id": session["session_id"]})
    _set_anon_cookie(response, new_anon_id)
    return response


@app.post("/api/sessions/{session_id}/claim")
async def claim_session(session_id: str, request: Request):
    username = _resolve_username(request)
    anonymous_id = (request.cookies.get("anon_session_id") or "").strip()
    if not username or not re.fullmatch(r"anon_[a-f0-9]{32}", anonymous_id):
        raise HTTPException(status_code=401, detail="Please sign in using the same browser.")
    session = await run_blocking(
        tutor_session_store.claim,
        session_id,
        owner_key(anonymous_id),
        owner_key(username),
        limit_concurrency=False,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Saved homework was not found or has expired.")
    return {"success": True, "session": session}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    session_owner, _new_anon_id = _request_session_owner(request)
    session = await run_blocking(
        tutor_session_store.get, session_id, session_owner, limit_concurrency=False
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.put("/api/sessions/{session_id}")
async def update_session(session_id: str, request: Request, body: SessionUpdateRequest):
    session_owner, _new_anon_id = _request_session_owner(request)
    try:
        session = await run_blocking(
            tutor_session_store.update,
            session_id,
            session_owner,
            body.model_dump(exclude_unset=True),
            limit_concurrency=False,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="Session changed; please reload.") from exc
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    session_owner, _new_anon_id = _request_session_owner(request)
    deleted = await run_blocking(
        tutor_session_store.delete, session_id, session_owner, limit_concurrency=False
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}

@app.post("/api/create-subscription")
async def create_subscription(request: SubscriptionRequest, req: Request):
    username = _resolve_username(req)
    if not username:
        raise HTTPException(status_code=401, detail="A parent or guardian needs to sign in.")
    if not _dev_mode:
        raise HTTPException(status_code=410, detail="Use secure Stripe Checkout for subscriptions.")
    duration_days = {"5_days": 5, "30_days": 30}
    if request.duration not in duration_days:
        raise HTTPException(status_code=400, detail="Invalid duration")
    from src.progress_db import create_local_subscription
    result = await run_blocking(
        create_local_subscription,
        username,
        request.name[:80],
        "5-Day Premium Access" if request.duration == "5_days" else "30-Day Premium Access",
        duration_days[request.duration],
        limit_concurrency=False,
    )
    return {"success": True, "subscription_id": result["subscription_id"], "duration": request.duration}

@app.get("/api/check-subscription")
async def check_subscription_api(req: Request, plan: Optional[str] = None):
    learner_id, username, new_anon_id = _get_user_or_anonymous_id(req)
    required_plans = [plan] if plan else None
    has_subscription = await run_blocking(
        user_has_subscription, req, learner_id, username, required_plans=required_plans, limit_concurrency=False
    )
    response = JSONResponse({
        "has_subscription": has_subscription,
        "student_id": learner_id,
        "logged_in": username is not None,
    })
    _set_anon_cookie(response, new_anon_id)
    return response

@app.post("/api/register")
async def api_register(request: AuthRequest):
    from src.progress_db import create_user
    from src.auth_tokens import generate_token

    username = request.get_username().strip().lower()
    if not re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", username) or len(username) > 254:
        raise HTTPException(status_code=400, detail="Please enter a valid parent or guardian email address.")
    if not (8 <= len(request.password) <= 128):
        raise HTTPException(status_code=400, detail="Use a password with at least 8 characters.")
    try:
        await run_blocking(create_user, username, request.password, limit_concurrency=False)
        account = await run_blocking(ensure_account, username, limit_concurrency=False)
        await run_blocking(ensure_default_student, account["id"], limit_concurrency=False)
        token = await run_blocking(generate_token, username, limit_concurrency=False)
    except ValueError as exc:
        if "already" in str(exc).lower():
            return JSONResponse(status_code=400, content={"success": False, "error": "This email is already registered. Please log in."})
        raise HTTPException(status_code=400, detail="The account could not be created.") from exc
    response = JSONResponse({"success": True, "username": username})
    response.set_cookie(
        "session", token, max_age=12 * 60 * 60, httponly=True,
        samesite="lax", secure=not _dev_mode,
    )
    return response

@app.post("/api/login")
async def api_login(request: AuthRequest):
    from src.progress_db import verify_user_credentials
    from src.auth_tokens import generate_token

    username = request.get_username().strip().lower()
    valid = bool(username) and await run_blocking(
        verify_user_credentials, username, request.password, limit_concurrency=False
    )
    if not valid:
        return JSONResponse(status_code=401, content={"success": False, "error": "Invalid email or password."})
    account = await run_blocking(ensure_account, username, limit_concurrency=False)
    await run_blocking(ensure_default_student, account["id"], limit_concurrency=False)
    token = await run_blocking(generate_token, username, limit_concurrency=False)
    response = JSONResponse({"success": True, "username": username})
    response.set_cookie(
        "session", token, max_age=12 * 60 * 60, httponly=True,
        samesite="lax", secure=not _dev_mode,
    )
    return response

@app.post("/api/logout")
async def api_logout(request: Request):
    token = _token_from_request(request)
    if token:
        from src.auth_tokens import revoke_token
        await run_blocking(revoke_token, token, limit_concurrency=False)
    response = JSONResponse({"success": True})
    response.delete_cookie("session", httponly=True, samesite="lax", secure=not _dev_mode)
    return response

@app.post("/api/upload-file")
async def upload_file(request: Request, file: UploadFile = File(...)):
    initialize()
    allowed = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_TEXT_EXTENSIONS | ALLOWED_PDF_EXTENSION
    filepath = None
    try:
        filepath = await stream_upload_to_temp(
            file,
            allowed_extensions=allowed,
            max_bytes=MAX_UPLOAD_BYTES,
            directory=UPLOAD_FOLDER,
        )
        content, is_image = await run_blocking(
            process_uploaded_file, filepath, limit_concurrency=False
        )
        return {"success": True, "content": content[:100_000], "is_image": is_image}
    except HTTPException:
        raise
    except Exception as exc:
        public_error(exc, "We could not read that file.")
        raise HTTPException(status_code=400, detail="We could not read that file. Please try a clear image, text file or PDF.") from exc
    finally:
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

@app.post("/api/upload-photo")
async def upload_photo(request: Request, request_body: PhotoRequest):
    initialize()
    if len(request_body.photo) > (MAX_UPLOAD_BYTES * 2):
        raise HTTPException(status_code=413, detail="That photo is too large.")
    try:
        content = await run_blocking(
            process_base64_image, request_body.photo, limit_concurrency=False
        )
        return {"success": True, "content": content[:100_000]}
    except Exception as exc:
        public_error(exc, "We could not read that photo.")
        raise HTTPException(status_code=400, detail="We could not read that photo. Please try a clearer one.") from exc

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


@app.get("/api/admin/access-status")
async def admin_access_status(request: Request):
    return {"success": True, "is_admin": bool(_require_admin(request))}


@app.get("/admin")
async def admin_page():
    return _static_page("static", "admin.html")


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
    """管理员手动创建订阅"""
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
            plan=request.plan or "homework_monthly",
        )
        return {"success": True, "subscription": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[Admin] 创建订阅失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


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
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


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

    # uvicorn.run(app, host="0.0.0.0", port=port, reload=True)
    uvicorn.run(
        "web_app:app", host="0.0.0.0", port=port, reload=_dev_mode,
        workers=1 if _dev_mode else int(os.getenv("WEB_CONCURRENCY", "2")),
        proxy_headers=runtime_settings.trust_proxy_headers,
    )


if __name__ == "__main__":
    main()