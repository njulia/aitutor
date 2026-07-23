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
import html
import re  # Ensure re is imported for regex operations
import json # Added: Import the json module
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, status  # Added Request and status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image
from src.progress_db import set_user_test_flag, is_user_test, get_user_by_username
from src.webapp.account_routes import build_account_router
from src.webapp.memory_routes import build_memory_router
from src.webapp.message_routes import create_message_router
from src.webapp.password_reset_routes import create_password_reset_router
from src.webapp.review_service import (
    review_homework as service_review_homework,
    explain_deep as service_explain_deep,
    improve_practice as service_improve_practice,
)
from src.webapp.runtime import install_hardening, owner_key, run_blocking
from src.webapp.session_store import TutorSessionStore
from src.webapp.stripe_pricing_billing import (
    billing_account_has_active_subscription,
    build_stripe_pricing_router,
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
    logger_init.warning(
        "STRIPE_SECRET_KEY is not set and DEV_MODE is off. "
        "Stripe Pricing Table checkout will remain unavailable."
    )

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

HOMEWORK_PREMIUM_PLAN = "homework_monthly"
ELEVENPLUS_PREMIUM_PLAN = "elevenplus_monthly"
PREMIUM_PLAN_NAMES = {
    HOMEWORK_PREMIUM_PLAN: "Homework Premium",
    ELEVENPLUS_PREMIUM_PLAN: "11+ Premium",
}


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
    """Warm up LLM on startup."""
    initialize()
    yield


def _resolve_username(req: Request) -> Optional[str]:
    """Return the authenticated parent email from a signed session token."""
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


def _require_admin(req: Request) -> str:
    """Require a signed-in parent account allow-listed for administration."""
    username = _resolve_username(req)
    if not username:
        raise HTTPException(status_code=401, detail="Administrator login is required.")

    configured = os.getenv("ADMIN_EMAILS") or os.getenv("ADMIN_EMAIL") or ""
    allowed = {item.strip().lower() for item in configured.split(",") if item.strip()}
    if allowed and username not in allowed:
        raise HTTPException(status_code=403, detail="This account is not an administrator.")
    if not allowed and not _dev_mode:
        raise HTTPException(status_code=403, detail="Administrator access is not configured.")
    return username


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


def _subscription_required_response(
    feature: str, plan: str, username: Optional[str]
) -> JSONResponse:
    plan_name = PREMIUM_PLAN_NAMES.get(plan, "Premium")
    if username is None:
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


def is_logged_in(req: Request) -> bool:
    """Check whether this request belongs to a registered parent account."""
    return _resolve_username(req) is not None


def user_has_subscription(
    req: Optional[Request] = None,
    student_id: Optional[str] = None,
    username: Optional[str] = None,
    required_plan: Optional[str] = None,
) -> bool:
    """Check the local entitlement state written by signed Stripe webhooks.

    Production requests never call Stripe directly, keeping paid learning
    features fast and available during a temporary Stripe API interruption.
    """
    # If student_id/username not provided, try to resolve from request
    if req and (student_id is None or username is None):
        resolved_student_id, resolved_username, _ = _get_user_or_anonymous_id(req)
        student_id = student_id or resolved_student_id
        username = username or resolved_username

    if student_id is None and username is None:
        return False

    try:
        if username:
            if is_user_test(username):
                return True

        # Anonymous IDs cannot have subscriptions
        if student_id and student_id.startswith("anon_"):
            return False

        if _dev_mode:
            from src.progress_db import get_local_subscriptions_by_email
            # 订阅表用 customer_email 关联，优先用 username（即 email）查找
            lookup_email = username or student_id
            if lookup_email and not lookup_email.startswith("anon_"):
                subs = get_local_subscriptions_by_email(lookup_email)
                for s in subs:
                    if s.get("status") == "active":
                        return True
            return False
        required_plans = [required_plan] if required_plan else None
        return bool(
            username
            and billing_account_has_active_subscription(
                username, required_plans=required_plans
            )
        )
    except Exception as e:
        logger.warning("Subscription check failed: %s", e)
        return False


app = FastAPI(
    title="Homework Magic",
    description="AI Tutor for UK Primary Schools",
    version="2.0.0",
    lifespan=lifespan,
)

# Parent-only Pricing Table session, customer portal and verified Stripe
# webhook routes. Checkout is never exposed to an anonymous learner session.
app.include_router(build_stripe_pricing_router(_resolve_username))

configured_cors_origins = os.getenv(
    "CORS_ORIGINS", "https://homeworkmagic.co.uk"
)
cors_origins = [
    item.strip().rstrip("/")
    for item in configured_cors_origins.split(",")
    if item.strip().startswith(("https://", "http://localhost", "http://127.0.0.1"))
]
if _dev_mode:
    cors_origins.extend(
        ["http://localhost:5000", "http://127.0.0.1:5000"]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(set(cors_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
    import tempfile

    if "base64," in data_url:
        data_url = data_url.split("base64,", 1)[1]

    image_data = base64.b64decode(data_url)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
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


_GUIDED_HOMEWORK_DIFFICULTY_LEVELS = {
    "gentle",
    "just_right",
    "challenge",
}
_GUIDED_HOMEWORK_MINUTES_TO_QUESTION_COUNT = {
    10: 5,
    15: 8,
    20: 10,
}
_GUIDED_ELEVEN_CONFIDENCE_LEVELS = {
    "confident",
    "sometimes_tricky",
    "needs_help",
}
_GUIDED_ELEVEN_EXAM_FORMATS = {
    "Not sure",
    "GL Assessment",
    "CEM",
    "ISEB Common Pre-Test",
    "School-specific",
}


def _clean_guided_text(value: Any, max_length: int) -> Optional[str]:
    """Minimise and bound an optional parent-entered learning note."""
    if value is None:
        return None
    from src.webapp.prompt_budget import compact_text

    cleaned = compact_text(value, max(40, max_length))
    return cleaned[:max_length].strip() or None


def normalise_guided_homework_profile(raw_profile: dict, student_id: str) -> dict:
    """Build a small, non-identifying profile from the Years 1-6 guide."""
    raw_profile = raw_profile or {}
    try:
        year_group = int(raw_profile.get("year_group", 3))
    except (TypeError, ValueError):
        year_group = 3
    year_group = min(6, max(1, year_group))

    try:
        requested_minutes = int(raw_profile.get("session_minutes", 15))
    except (TypeError, ValueError):
        requested_minutes = 15
    session_minutes = (
        requested_minutes
        if requested_minutes in _GUIDED_HOMEWORK_MINUTES_TO_QUESTION_COUNT
        else 15
    )

    difficulty = str(raw_profile.get("difficulty", "just_right"))
    if difficulty not in _GUIDED_HOMEWORK_DIFFICULTY_LEVELS:
        difficulty = "just_right"

    from src.models import canonical_primary_subject

    subject = canonical_primary_subject(
        _clean_guided_text(raw_profile.get("subject"), 60) or ""
    ) or "Maths"
    learning_notes = _clean_guided_text(raw_profile.get("learning_notes"), 300)

    support_message = {
        "gentle": (
            "Begin with short confidence-building questions and increase "
            "difficulty only a little."
        ),
        "just_right": (
            "Use age-appropriate questions with a gentle increase in difficulty."
        ),
        "challenge": (
            "Use a short warm-up, then include an age-appropriate challenge."
        ),
    }[difficulty]
    learning_needs = support_message
    if learning_notes:
        learning_needs = f"{support_message} Parent learning note: {learning_notes}"

    profile = {
        "setup_source": "guided_homework",
        "year_group": year_group,
        "age": year_group + 5,
        "subject": subject,
        "difficulty": difficulty,
        "question_count": _GUIDED_HOMEWORK_MINUTES_TO_QUESTION_COUNT[session_minutes],
        "preferred_session_minutes": session_minutes,
        "learning_needs": learning_needs,
        "learning_goals": [
            f"Practise {subject} at Year {year_group} curriculum level."
        ],
        "student_id": student_id,
    }
    return profile


def guided_homework_client_profile(profile: dict) -> dict:
    """Return the daily choices without identifiers or parent free text."""
    allowed = (
        "setup_source",
        "year_group",
        "age",
        "subject",
        "difficulty",
        "question_count",
        "preferred_session_minutes",
        "learning_goals",
    )
    return {
        key: profile[key]
        for key in allowed
        if key in profile and profile[key] not in (None, "")
    }


def normalise_guided_eleven_profile(raw_profile: dict, student_id: str) -> dict:
    """Build a small, non-identifying profile from the guided 11+ choices."""
    raw_profile = raw_profile or {}
    try:
        year_group = int(raw_profile.get("year_group", 5))
    except (TypeError, ValueError):
        year_group = 5
    year_group = min(6, max(3, year_group))

    try:
        requested_count = int(raw_profile.get("question_count", 8))
    except (TypeError, ValueError):
        requested_count = 8
    question_count = 5 if requested_count <= 5 else 8

    confidence = str(raw_profile.get("confidence", "sometimes_tricky"))
    if confidence not in _GUIDED_ELEVEN_CONFIDENCE_LEVELS:
        confidence = "sometimes_tricky"

    exam_format = str(raw_profile.get("exam_format", "Not sure"))
    if exam_format not in _GUIDED_ELEVEN_EXAM_FORMATS:
        exam_format = "Not sure"

    from src.models import ELEVEN_PLUS_SUBJECTS

    subject = _clean_guided_text(raw_profile.get("subject"), 60) or "Maths"
    if subject not in ELEVEN_PLUS_SUBJECTS:
        subject = "Maths"
    learning_notes = _clean_guided_text(raw_profile.get("learning_notes"), 300)

    exam_month = None
    raw_exam_date = str(raw_profile.get("exam_date") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_exam_date):
        try:
            exam_month = datetime.strptime(raw_exam_date, "%Y-%m-%d").strftime("%B %Y")
        except ValueError:
            exam_month = None

    support_message = {
        "confident": "Begin briskly and include an age-appropriate challenge.",
        "sometimes_tricky": "Use gradual difficulty and short, clear wording.",
        "needs_help": "Start gently and build confidence before increasing difficulty.",
    }[confidence]
    learning_needs = support_message
    if learning_notes:
        learning_needs = f"{support_message} Parent learning note: {learning_notes}"

    learning_goals = [f"Practise {subject} for the 11+."]
    if exam_format != "Not sure":
        learning_goals.append(f"Use {exam_format} style where suitable.")
    if exam_month:
        learning_goals.append(f"Build confidence before {exam_month}.")

    profile = {
        "setup_source": "guided_11plus",
        "year_group": year_group,
        "age": year_group + 5,
        "subject": subject,
        "confidence": confidence,
        "question_count": question_count,
        "exam_format": exam_format,
        "learning_needs": learning_needs,
        "learning_goals": learning_goals,
        "preferred_session_minutes": 10 if question_count == 5 else 15,
        "student_id": student_id,
    }
    if confidence == "needs_help":
        profile["weak_areas"] = [subject]
    if exam_month:
        profile["exam_month"] = exam_month
    return profile


def guided_eleven_client_profile(profile: dict) -> dict:
    """Return useful guided choices without identifiers or parent free text."""
    allowed = (
        "setup_source",
        "year_group",
        "age",
        "subject",
        "confidence",
        "question_count",
        "exam_format",
        "exam_month",
        "learning_goals",
        "preferred_session_minutes",
    )
    return {
        key: profile[key]
        for key in allowed
        if key in profile and profile[key] not in (None, "")
    }


def _format_public_question_subset(questions: list) -> str:
    """Convert a bounded structured question list back to answer-free text."""
    blocks: List[str] = []
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue
        lines: List[str] = []
        context = str(question.get("context") or "").strip()
        if context:
            lines.append(context)
        prompt = str(question.get("question") or "").strip()
        if not prompt:
            continue
        lines.append(f"{index}. {prompt}")
        for option in question.get("options") or []:
            if not isinstance(option, dict):
                continue
            label = str(option.get("label") or "").strip()
            text = str(option.get("text") or "").strip()
            if label and text:
                lines.append(f"{label}) {text}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def limit_homework_question_count(homework_results: list, question_count: Optional[int]) -> list:
    """Limit public worksheet questions without exposing stored answer material."""
    if not question_count:
        return homework_results
    limit = max(1, min(int(question_count), 20))
    limited_results = []
    for result in homework_results:
        if not isinstance(result, dict):
            limited_results.append(result)
            continue
        item = dict(result)
        questions = item.get("questions")
        if isinstance(questions, list) and questions:
            limited_questions = [dict(question) for question in questions[:limit]]
            for index, question in enumerate(limited_questions, start=1):
                question["number"] = index
            item["questions"] = limited_questions
            limited_content = _format_public_question_subset(limited_questions)
            if limited_content:
                item["content"] = limited_content
        limited_results.append(item)
    return limited_results


def _get_user_or_anonymous_id(req: Request) -> tuple[str, Optional[str], Optional[str]]:
    """
    Determines the student_id and username for the current request.
    Returns (student_id, username_if_logged_in, new_anonymous_session_id_to_set_in_cookie).
    new_anonymous_session_id_to_set_in_cookie will be None if no new cookie is needed.
    """
    # 1. Check for logged-in user
    username = _resolve_username(req)
    if username:
        # Billing belongs to the parent account, while learning records belong
        # to a pseudonymous learner profile. Never use an email as a learner ID.
        from src.webapp.account_store import ensure_account, ensure_default_student

        account = ensure_account(username)
        learner = ensure_default_student(account["id"])
        return str(learner["id"]), username, None

    # 2. Check for anonymous session ID cookie
    anonymous_session_id = req.cookies.get("anon_session_id")
    if anonymous_session_id:
        return anonymous_session_id, None, None # No username for anonymous

    # 3. Generate a new anonymous session ID
    new_anon_session_id = f"anon_{uuid.uuid4().hex}" # Prefix to distinguish from real student_ids
    return new_anon_session_id, None, new_anon_session_id


# Register the account-owned pages and APIs that are implemented in ``src/webapp``.
# These routers were present in the Stripe-enabled archive but were not attached
# to the FastAPI application, which made learning memory and account APIs return
# 404 responses.
app.include_router(
    create_message_router(
        resolve_identity=_get_user_or_anonymous_id,
        require_admin=_require_admin,
        project_root=project_root,
    )
)
app.include_router(
    build_account_router(
        resolve_username=_resolve_username,
        require_admin=_require_admin,
        session_store=tutor_session_store,
    )
)
app.include_router(build_memory_router(_resolve_username))
app.include_router(
    create_password_reset_router(project_root=project_root, dev_mode=_dev_mode)
)


def generate_homework_with_profile(profile: dict, subjects: list, is_eleven_plus: bool = False):
    """为多个科目生成作业（并行执行以降低延迟）"""
    from src.homework_generator import generate_homework_parallel

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 3)}_default"

    return generate_homework_parallel(profile, subjects, llm, is_eleven_plus=is_eleven_plus)


def _split_homework_into_questions(homework_content: str, subject: str) -> List[Dict[str, str]]:
    """
    Splits a block of homework content into individual questions.
    Assumes questions are numbered (e.g., 1., 2., (1), (2), or bullet points).
    """
    extracted_questions = []
    
    # Normalize newlines and strip leading/trailing whitespace
    homework_content = homework_content.strip().replace('\r\n', '\n')

    # --- Attempt to split by numbered questions first ---
    # This pattern splits on the start of a new numbered question (e.g., "1. ", "2. ")
    # The capturing group `(\d+\.)` means the delimiter itself will be included in the split list.
    numbered_parts = re.split(r'(?m)^\s*(\d+\.)[\s\xa0]+', homework_content)

    # If the first part is not a delimiter, it's either a header or unnumbered intro.
    # If there are subsequent numbered questions (i.e., len(numbered_parts) > 1),
    # we can assume the first part is a header/intro to be discarded.
    if numbered_parts and numbered_parts[0].strip() and len(numbered_parts) > 1 and not re.match(r'^\s*\d+\.', numbered_parts[0]):
        logger.debug(f"Discarding unnumbered intro/header before first numbered question: '{numbered_parts[0].strip()}'")
        numbered_parts = numbered_parts[1:] # Discard the intro part

    i = 0
    while i < len(numbered_parts):
        if re.match(r'^\s*\d+\.', numbered_parts[i]):  # This is a delimiter (e.g., "1.")
            question_number_prefix = numbered_parts[i].strip()
            question_text_segment = numbered_parts[i + 1].strip() if i + 1 < len(numbered_parts) else ""
            
            # Combine prefix and text segment to form the full question content (for RAG)
            full_question_content = f"{question_number_prefix} {question_text_segment}".strip()
            
            extracted_questions.append({
                "subject": subject,
                "content": question_text_segment,
                "full_content": full_question_content,
                "original_full_content": homework_content # This is the content *after* potential initial header removal
            })
            i += 2
        else: # This branch should ideally only be hit if the content is malformed or not numbered.
              # If it's the very first part and we didn't discard it, it's a standalone unnumbered block.
            if numbered_parts[i].strip():
                # If no questions have been added yet, treat this as the first question
                if not extracted_questions: 
                     extracted_questions.append({
                        "subject": subject,
                        "content": numbered_parts[i].strip(),
                        "full_content": numbered_parts[i].strip(),
                        "original_full_content": homework_content
                    })
                else: # This is an unexpected unnumbered block in between or after numbered questions
                    logger.warning(f"Unexpected unnumbered part in homework content after split: '{numbered_parts[i].strip()}'")
                    extracted_questions.append({
                        "subject": subject,
                        "content": numbered_parts[i].strip(),
                        "full_content": numbered_parts[i].strip(),
                        "original_full_content": homework_content
                    })
            i += 1

    # If no questions were found from numbered patterns, try bullet points
    if not extracted_questions:
        bullet_parts = re.split(r'(?m)^\s*([-*])[\s\xa0]+', homework_content)
        # Similar logic for discarding initial unbulleted intro/header
        if bullet_parts and bullet_parts[0].strip() and len(bullet_parts) > 1 and not re.match(r'^\s*[-*]', bullet_parts[0].strip()):
            logger.debug(f"Discarding unbulleted intro/header before first bullet question: '{bullet_parts[0].strip()}'")
            bullet_parts = bullet_parts[1:]

        i = 0
        while i < len(bullet_parts):
            if re.match(r'^\s*[-*]', bullet_parts[i].strip()): # This is a delimiter (e.g., "-")
                bullet_prefix = bullet_parts[i].strip()
                bullet_text_segment = bullet_parts[i + 1].strip() if i + 1 < len(bullet_parts) else ""
                full_bullet_content = f"{bullet_prefix} {bullet_text_segment}".strip()
                extracted_questions.append({
                    "subject": subject,
                    "content": bullet_text_segment,
                    "full_content": full_bullet_content,
                    "original_full_content": homework_content
                })
                i += 2
            else:
                if bullet_parts[i].strip():
                    if not extracted_questions: # If no questions yet, treat as first
                        extracted_questions.append({
                            "subject": subject,
                            "content": bullet_parts[i].strip(),
                            "full_content": bullet_parts[i].strip(),
                            "original_full_content": homework_content
                        })
                    else: # Unexpected unbulleted block
                        logger.warning(f"Unexpected unbulleted part in homework content after split: '{bullet_parts[i].strip()}'")
                        extracted_questions.append({
                            "subject": subject,
                            "content": bullet_parts[i].strip(),
                            "full_content": bullet_parts[i].strip(),
                            "original_full_content": homework_content
                        })
                i += 1

    # If still no clear split, treat the whole content as one question
    if not extracted_questions and homework_content.strip():
        extracted_questions.append({
            "subject": subject,
            "content": homework_content.strip(),
            "full_content": homework_content.strip(),
            "original_full_content": homework_content
        })

    # Filter out any empty content questions that might arise from splitting
    extracted_questions = [q for q in extracted_questions if q["content"].strip()]

    # Assign unique IDs to each question
    for i, q in enumerate(extracted_questions):
        q["question_id"] = f"{subject}_{uuid.uuid4().hex[:8]}_{i + 1}"

    return extracted_questions


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


def review_homework(homework_content: str, student_answers: str, subject: str, profile=None,
                    is_tutor_mode: bool = False, homework_doc_id: str = None, is_eleven_plus: bool = False):
    """批改作业 - 优先从 RAG 读取正确答案，否则使用 LLM 生成"""
    from src.llm_client import format_prompt, build_messages
    from src.prompts import REVIEW_HOMEWORK_PROMPT, REVIEW_TUTOR_QUESTION_PROMPT
    from src.cache import review_cache, make_cache_key

    if profile is None:
        profile = {"year_group": 3, "age": 7}

    # Determine which prompt to use
    prompt_template = REVIEW_TUTOR_QUESTION_PROMPT if is_tutor_mode else REVIEW_HOMEWORK_PROMPT

    # Cache key needs to differentiate between tutor mode and homework mode
    cache_key_prefix = "review_tutor" if is_tutor_mode else "review_homework"
    cache_key = make_cache_key(cache_key_prefix, subject, str(profile.get("year_group", 3)),
                               homework_content[:200], student_answers[:200])
    cached = review_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中批改缓存 (%s)", cache_key_prefix)
        return {"success": True, "review": cached, "from_cache": True}

    try:
        # 1. 优先从 RAG 中读取正确答案（零 LLM 调用）
        rag_answers = None
        correct_answers_section = ""
        generated_table_markdown = ""  # New variable for the Python-generated table

        # Default feedback instruction (LLM will generate this part)
        # This will be used by the prompt template for the LLM's general feedback.
        feedback_instruction_for_llm = """- What the student did well
                    - Areas that need correction or improvement
                    - Specific feedback for each task"""

        if homework_doc_id:
            try:
                if is_eleven_plus:
                    from src.elevenplus.elevenplus_rag import search_homework_answers as _search_answers
                else:
                    from src.homework_rag import search_homework_answers as _search_answers
                
                raw_rag_answers = _search_answers(homework_doc_id)
                
                # Split homework_content into questions (needed for pairing and mapping)
                parsed_questions = _split_homework_into_questions(homework_content, subject)

                processed_rag_answers = []
                if isinstance(raw_rag_answers, list) and all(isinstance(item, str) for item in raw_rag_answers):
                    # Case: raw_rag_answers is a list of strings (just answers)
                    logger.info("[RAG] Received raw answers as list of strings. Attempting to pair with questions from homework_content.")
                    
                    # Pair questions with answers
                    for i, q_dict in enumerate(parsed_questions):
                        # Use full_content (with numbering) if available for RAG pairing
                        question_to_check = q_dict.get("full_content", q_dict["content"]).strip()
                        
                        # Only include if it looks like a question (numbered or bulleted)
                        if re.match(r'^\s*(\d+\.|\(|\*|-)', question_to_check):
                            if i < len(raw_rag_answers):
                                processed_rag_answers.append({
                                    "question": question_to_check,
                                    "answer": raw_rag_answers[i].strip()
                                })
                            else:
                                # Handle cases where there are more questions than answers
                                processed_rag_answers.append({
                                    "question": question_to_check,
                                    "answer": "No correct answer found" # Placeholder
                                })
                        else:
                            logger.debug(f"[RAG] Skipping non-question item from homework_content: {question_to_check}")
                    rag_answers = processed_rag_answers
                elif isinstance(raw_rag_answers, list) and all(isinstance(item, dict) and "question" in item and "answer" in item for item in raw_rag_answers):
                    # Case: raw_rag_answers is already a list of dictionaries (question-answer pairs)
                    logger.info("[RAG] Received raw answers as list of question-answer dictionaries.")
                    
                    if is_tutor_mode and len(parsed_questions) == 1:
                        # Special Case: Tutor mode often reviews a single question.
                        # We need to find this specific question in the RAG answers.
                        target_q = parsed_questions[0]["content"].strip().lower()
                        target_q_full = parsed_questions[0].get("full_content", "").strip().lower()
                        
                        found_item = None
                        for item in raw_rag_answers:
                            rag_q = item["question"].strip().lower()
                            # Try matching full content, stripped content, or substring
                            if target_q_full == rag_q or target_q == rag_q:
                                found_item = item
                                break
                            # Robust matching: strip numbering from RAG question for comparison
                            rag_q_stripped = re.sub(r'^\s*(\d+\.|\(|\*|-)\s*', '', item["question"]).strip().lower()
                            if target_q == rag_q_stripped:
                                found_item = item
                                break
                        
                        if found_item:
                            logger.info("[RAG] Matched single question to RAG answer.")
                            processed_rag_answers.append(found_item)
                        else:
                            logger.warning("[RAG] Could not match tutor question to any RAG question. target_q: %s", target_q)
                    else:
                        # Regular filtering
                        for item in raw_rag_answers:
                            # RAG answers in dict format already have the question text (likely with number)
                            question_text = item["question"].strip()
                            if re.match(r'^\s*(\d+\.|\(|\*|-)', question_text): 
                                processed_rag_answers.append(item)
                            else:
                                logger.debug(f"[RAG] Filtering out non-question item from RAG answers: {question_text}")
                    rag_answers = processed_rag_answers
                else:
                    # Unexpected format, treat as no RAG answers found
                    logger.warning("[RAG] _search_answers returned unexpected format: %s. Expected list of strings or list of dicts with 'question' and 'answer'.", type(raw_rag_answers))
                    rag_answers = None

                if rag_answers:
                    # 将正确答案和学生答案一起发给 LLM 做简洁对比
                    logger.info("[RAG] Found correct answers for doc_id=%s. Building comparison table.",
                                homework_doc_id)

                    # Extract questions from RAG answers for mapping
                    rag_questions_list = [item["question"].strip() for item in rag_answers]

                    # Heuristically parse student answers and map them to RAG questions for the current subject
                    student_answers_map = _parse_student_answers_to_map(student_answers, subject, rag_questions_list)

                    # Build the table rows
                    table_rows_data = []
                    # Create a mapping from question content (without numbers) to full content (with numbers) if possible
                    # This helps in case student_answers_map used the stripped content
                    content_to_full = {q["content"].strip(): q["full_content"].strip() for q in parsed_questions if "full_content" in q}

                    for rag_item in rag_answers:
                        q_text = rag_item["question"].strip()
                        correct_ans = rag_item["answer"].strip()

                        # Try to get student answer using the full question text (with number)
                        student_ans = student_answers_map.get(q_text)
                        
                        # Fallback: if student_answers_map used stripped text, try that
                        if student_ans is None:
                            # Find the stripped version of q_text if it has a number
                            # This is a bit tricky, but since q_text came from RAG, it likely HAS a number.
                            # We can try to match it against our parsed questions.
                            for p_q in parsed_questions:
                                if p_q.get("full_content", "").strip() == q_text:
                                    student_ans = student_answers_map.get(p_q["content"].strip())
                                    break
                        
                        if student_ans is None:
                            student_ans = "No answer provided"

                        student_ans = student_ans.strip()

                        # Escape pipe characters in answers to avoid breaking markdown table
                        # Determine if correct
                        if subject == "Maths":
                            from src.tools.math_tools import verify_math_answer
                            verification = verify_math_answer(q_text, student_ans, correct_ans)
                            is_correct = verification["is_correct"]
                        else:
                            is_correct = (student_ans.lower() == correct_ans.lower()) # Simple string comparison for now
                        
                        status_icon = "✅" if is_correct else "❌"

                        student_ans_escaped = student_ans.replace('|', '\\|')
                        correct_ans_escaped = correct_ans.replace('|', '\\|')
                        q_text_escaped = q_text.replace('|', '\\|')

                        table_rows_data.append([status_icon, q_text_escaped, student_ans_escaped, correct_ans_escaped])

                    if table_rows_data:
                        table_header = "| Status | Question | Your Answer | Correct Answer |\n|---|---|---|---|\n"
                        table_content = "\n".join(["| " + " | ".join(row) + " |" for row in table_rows_data])
                        generated_table_markdown = f"\n\n## Homework Review Summary\n{table_header}{table_content}\n\n"

                    # The `correct_answers_section` can still be passed to LLM for context

                    correct_answers_text = json.dumps(rag_answers, ensure_ascii=False) if isinstance(rag_answers, (list,
                                                                                                                   dict)) else str(
                        rag_answers)
                    correct_answers_section = f"\n\n## Correct Answers (for LLM context):\n```json\n{correct_answers_text}\n```\n"

                else:
                    logger.info("[Review] No correct answers found in RAG for doc_id=%s. Using LLM for full review.", homework_doc_id)

            except Exception as e:
                logger.warning("[RAG] Failed to retrieve correct answers or build table: %s", e)
                logger.info(
                    "[Review] Falling back to LLM for full review due to RAG error. No comparison table will be generated.")

        prompt_text = format_prompt(
            prompt_template,
            student_profile=str(profile),
            subject=subject,
            day=datetime.now().strftime("%A, %B %d, %Y"),
            homework_content=homework_content,
            student_answer=student_answers,
            correct_answers_section=correct_answers_section,
            feedback_instruction = feedback_instruction_for_llm  # Use the general instruction for LLM
        )
        messages = build_messages(prompt_text)
        llm_result = llm.complete(messages)  # Get LLM's general feedback
        # Combine Python-generated table with LLM's response
        final_review_result = generated_table_markdown + llm_result

        # 写入缓存
        review_cache.set(cache_key, final_review_result)

        # 保存进度到数据库 (Only save for full homework sessions, not individual tutor questions)
        if not is_tutor_mode:
            try:
                from src.progress_db import save_homework_session
                # 从 review 文本中提取分数（如 "Score: 7/10" 或 "7/10"）
                score_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+)", llm_result)  # Score is in LLM's part
                score = float(score_match.group(1)) if score_match else None

                student_id = profile.get("student_id", "anonymous")
                save_homework_session(
                    student_id=student_id,
                    subject=subject,
                    year_group=profile.get("year_group", 3),
                    homework_content=homework_content,
                    student_answers=student_answers,  # Original student answers
                    score=score,
                    review_text=final_review_result,  # Save the combined review
                )

            except Exception as db_exc:
                logger.warning("Failed to save progress: %s", db_exc)

        return {"success": True, "review": final_review_result, "from_rag_answers": rag_answers is not None}
    except Exception as exc:
        logger.error("Error reviewing homework: %s", exc)
        return {"success": False, "error": str(exc)}


def explain_deep(homework_content: str, student_answers: str, subject: str,
                 profile=None, review_feedback: str = ""):
    """深度解释作业答案 - 使用 EXPLAIN_DEEP_PROMPT 生成逐步解释、薄弱点分析等"""
    from src.llm_client import format_prompt, build_messages
    from src.prompts import EXPLAIN_DEEP_PROMPT
    from src.cache import explain_cache, make_cache_key

    if profile is None:
        profile = {"year_group": 3, "age": 7}

    # 检查缓存
    cache_key = make_cache_key("explain", subject, str(profile.get("year_group", 3)),
                               homework_content[:200], student_answers[:200])
    cached = explain_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中深度解释缓存")
        return {"success": True, "explanation": cached, "from_cache": True}

    try:
        prompt_text = format_prompt(
            EXPLAIN_DEEP_PROMPT,
            homework_content=homework_content,
            student_answer=student_answers,
            subject=subject,
            student_profile=str(profile),
            review_feedback=review_feedback or "No review feedback available",
            year_group=profile.get("year_group", 3),
            age=profile.get("age", 7),
        )
        messages = build_messages(prompt_text)
        result = llm.complete(messages)

        # 写入缓存
        explain_cache.set(cache_key, result)

        return {"success": True, "explanation": result}
    except Exception as exc:
        logger.error("Error in explain_deep: %s", exc)
        return {"success": False, "error": str(exc)}


def improve_practice(homework_content: str, student_answers: str, subject: str,
                     profile=None, review_feedback: str = ""):
    """根据学生的弱项生成针对性练习 - 使用 IMPROVE_PRACTICE_PROMPT"""
    from src.llm_client import format_prompt, build_messages
    from src.prompts import IMPROVE_PRACTICE_PROMPT
    from src.cache import practice_cache, make_cache_key

    if profile is None:
        profile = {"year_group": 3, "age": 7}

    # 检查缓存
    cache_key = make_cache_key("practice", subject, str(profile.get("year_group", 3)),
                               homework_content[:200], student_answers[:200])
    cached = practice_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中练习生成缓存")
        return {"success": True, "practice": cached, "from_cache": True}

    try:
        prompt_text = format_prompt(
            IMPROVE_PRACTICE_PROMPT,
            homework_content=homework_content,
            student_answer=student_answers,
            subject=subject,
            student_profile=str(profile),
            review_feedback=review_feedback or "No review feedback available",
            year_group=profile.get("year_group", 3),
            age=profile.get("age", 7),
        )
        messages = build_messages(prompt_text)
        result = llm.complete(messages)

        # 写入缓存
        practice_cache.set(cache_key, result)

        return {"success": True, "practice": result}
    except Exception as exc:
        logger.error("Error in improve_practice: %s", exc)
        return {"success": False, "error": str(exc)}


# Use the maintained review implementation for every live endpoint. The legacy
# functions above are retained temporarily for source compatibility, but they do
# not understand the newer RAG prompt fields or model-routing flags.
def review_homework(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile=None,
    *,
    quick_review: bool = False,
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


def _public_legal_page(filename: str) -> HTMLResponse:
    """Render public operator details without exposing unexpanded markers."""
    path = os.path.join(project_root, "static", filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Page not found")
    with open(path, encoding="utf-8") as source:
        content = source.read()

    def escaped_env(name: str, fallback: str) -> str:
        return html.escape(os.getenv(name, fallback), quote=True)

    def optional_line(label: str, name: str) -> str:
        value = str(os.getenv(name, "")).strip()
        if not value:
            return ""
        return f"<br>{html.escape(label)}: {html.escape(value, quote=True)}"

    contact_email = (
        os.getenv("BUSINESS_CONTACT_EMAIL")
        or os.getenv("PRIVACY_CONTACT_EMAIL")
        or "contact@homeworkmagic.co.uk"
    )
    replacements = {
        "{{DATA_CONTROLLER_NAME}}": escaped_env(
            "DATA_CONTROLLER_NAME", "[Add the legal operator name before launch]"
        ),
        "{{BUSINESS_CONTACT_EMAIL}}": html.escape(contact_email, quote=True),
        "{{PRIVACY_CONTACT_EMAIL}}": escaped_env(
            "PRIVACY_CONTACT_EMAIL", contact_email
        ),
        "{{PRIVACY_POSTAL_ADDRESS}}": escaped_env(
            "PRIVACY_POSTAL_ADDRESS", "[Add a postal contact address before launch]"
        ),
        "{{BUSINESS_SUPPORT_PHONE_LINE}}": optional_line(
            "Phone", "BUSINESS_SUPPORT_PHONE"
        ),
        "{{BUSINESS_REGISTRATION_LINE}}": optional_line(
            "Company registration number", "BUSINESS_REGISTRATION_NUMBER"
        ),
        "{{BUSINESS_VAT_STATUS_LINE}}": optional_line(
            "VAT status", "BUSINESS_VAT_STATUS"
        ),
    }
    for marker, value in replacements.items():
        content = content.replace(marker, value)
    return HTMLResponse(
        content,
        headers={"Cache-Control": "public, max-age=300"},
    )


class ProfileRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    subjects: list = Field(default_factory=list)
    quick_select: bool = False
    year: Optional[int] = None
    student_id: Optional[str] = None
    is_eleven_plus: bool = False
    mode: Optional[str] = "homework"  # Added mode field
    question_count: Optional[int] = Field(default=None, ge=1, le=20)


class ReviewRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    session_id: Optional[str] = None
    quick_review: bool = False
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
    duration: str  # "5_days" or "1_month"
    plan: str = HOMEWORK_PREMIUM_PLAN


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    year_group: Optional[int] = None
    age: Optional[int] = None
    is_active: Optional[bool] = None


class SubscriptionRequest(BaseModel):
    email: str
    name: str
    duration: str  # "5_days" or "1_month"


class AuthRequest(BaseModel):
    username: str = None
    email: str = None
    password: str

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
async def pricing_page():
    return _public_legal_page("pricing.html")


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


@app.get("/progress")
async def progress_page():
    return _static_page("static", "progress.html")


@app.get("/memory")
async def memory_page():
    return _static_page("static", "memory.html")


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


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Serve crawler rules from the application root.

    Cloud Run does not automatically expose project-root files, so an explicit
    route is required even when ``robots.txt`` is included in the container.
    """
    robots_path = os.path.join(project_root, "robots.txt")
    if os.path.isfile(robots_path):
        return FileResponse(robots_path, media_type="text/plain; charset=utf-8")

    # Safe production fallback if the deployment image omits the text file.
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /uploads/\n"
        "Disallow: /api/\n\n"
        "Sitemap: https://homeworkmagic.co.uk/sitemap.xml\n"
    )


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    # The current production bundle stores the sitemap directly under static/.
    # Keep the legacy --seo location as a fallback for older deployments.
    sitemap_candidates = (
        os.path.join(project_root, "static", "sitemap.xml"),
        os.path.join(project_root, "static", "--seo", "sitemap.xml"),
    )
    for sitemap_path in sitemap_candidates:
        if os.path.isfile(sitemap_path):
            return FileResponse(sitemap_path, media_type="application/xml")
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
    return {"status": "ok", "initialized": initialized}


@app.get("/api/client-id")
async def get_client_id(request: Request):
    """Return an account-owned learner ID or a random cookie-backed anonymous ID."""
    resolved_id, _username, new_anon_id = _get_user_or_anonymous_id(request)
    response = JSONResponse({"client_id": resolved_id})
    if new_anon_id:
        response.set_cookie(
            "anon_session_id",
            new_anon_id,
            httponly=True,
            samesite="lax",
            secure=not _dev_mode,
            max_age=365 * 24 * 60 * 60,
        )
    return response


@app.get("/api/subjects")
async def get_subjects():
    from src.models import UK_PRIMARY_SUBJECTS, ELEVEN_PLUS_SUBJECTS

    return {"primary": UK_PRIMARY_SUBJECTS, "eleven_plus": ELEVEN_PLUS_SUBJECTS}


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
    try:
        initialize()

        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        # Override the student_id in the request with the resolved one
        request.student_id = resolved_student_id
        if request.profile:
            request.profile["student_id"] = resolved_student_id
        else:
            request.profile = {"student_id": resolved_student_id}

        is_guided_eleven = (
            request.is_eleven_plus
            and request.profile.get("setup_source") == "guided_11plus"
        )
        is_guided_homework = (
            not request.is_eleven_plus
            and request.profile.get("setup_source") == "guided_homework"
        )
        if is_guided_eleven:
            profile = normalise_guided_eleven_profile(
                request.profile,
                resolved_student_id,
            )
        elif is_guided_homework:
            profile = normalise_guided_homework_profile(
                request.profile,
                resolved_student_id,
            )
        else:
            profile = resolve_profile(
                request.profile,
                quick_select=request.quick_select,
                year=request.year,
                student_id=request.student_id,
            )

        subjects = list(request.subjects or [])
        if is_guided_eleven:
            subjects = [profile["subject"]]
        elif is_guided_homework:
            subjects = [profile["subject"]]

        mode = request.mode if request.mode in {"homework", "tutor"} else "homework"
        question_limit = request.question_count
        if is_guided_eleven:
            question_limit = profile["question_count"]

            if not user_has_subscription(
                req=req,
                student_id=resolved_student_id,
                username=logged_in_username,
                required_plan=ELEVENPLUS_PREMIUM_PLAN,
            ):
                response = _subscription_required_response(
                    "Guided 11+ Practice",
                    ELEVENPLUS_PREMIUM_PLAN,
                    logged_in_username,
                )
                if new_anon_session_id:
                    response.set_cookie(
                        "anon_session_id",
                        new_anon_session_id,
                        httponly=True,
                        samesite="lax",
                        secure=not _dev_mode,
                        max_age=365 * 24 * 60 * 60,
                    )
                return response
        elif is_guided_homework:
            question_limit = profile["question_count"]

        # If no subjects selected, use LLM to extract from description
        if not subjects:
            description = ""
            if request.profile:
                description = request.profile.get("description", "")
            # Fallback to profile description if request.profile is None
            description = description or profile.get("description", "")
            if description:
                from src.ui.shared import parse_profile_from_natural_language
                # 放到线程池执行，避免阻塞事件循环
                parsed = await asyncio.to_thread(parse_profile_from_natural_language, description, llm)
                if parsed:
                    # Update profile with parsed data
                    profile.update(parsed)
                    subjects = parsed.get("extracted_subjects", [])
                    logger.info("[Generate] LLM extracted subjects from description: %s", subjects)

            if not subjects:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "No subjects selected. Please select subjects or provide a description for AI analysis."},
                )

        # Generate homework for all subjects（放到线程池执行，避免阻塞事件循环）
        all_homework_results = await asyncio.to_thread(
            generate_homework_with_profile, profile, subjects, request.is_eleven_plus
        )
        for result in all_homework_results:
            if isinstance(result, dict):
                result["is_eleven_plus"] = bool(request.is_eleven_plus)

        if is_guided_eleven:
            client_profile = guided_eleven_client_profile(profile)
        elif is_guided_homework:
            client_profile = guided_homework_client_profile(profile)
        else:
            client_profile = profile

        if mode == "tutor":
            individual_questions = []
            for hw_block in all_homework_results:
                # Split each subject's homework content into individual questions
                split_questions = _split_homework_into_questions(hw_block["content"], hw_block["subject"])
                # Preserve RAG metadata on each split question
                for q in split_questions:
                    q["doc_id"] = hw_block.get("doc_id")
                    q["from_rag"] = bool(hw_block.get("from_rag", False))
                    q["is_eleven_plus"] = bool(request.is_eleven_plus)
                individual_questions.extend(split_questions)

            # Check subscription for tutor mode (only for non-RAG questions)
            has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
            
            if not has_sub:
                # Filter out non-RAG questions if not subscribed
                rag_only_questions = [q for q in individual_questions if q.get("from_rag")]
                if question_limit:
                    rag_only_questions = rag_only_questions[:question_limit]
                if rag_only_questions:
                    response_content = {"success": True, "homework": rag_only_questions, "profile": client_profile, "mode": "tutor",
                                        "note": "Partial results: only RAG-sourced questions (free). Subscribe for full tutor mode."}
                    resp = JSONResponse(content=response_content)
                    if new_anon_session_id:
                        resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
                    return resp
                else:
                    # No RAG questions and no subscription for tutor mode
                    if logged_in_username is None:
                        return JSONResponse(status_code=401, content={"success": False,
                                                                      "error": "Login required to access tutor mode for AI-generated questions."})
                    return JSONResponse(status_code=402,
                                        content={"success": False, "error": "Tutor mode for AI-generated questions requires an active subscription."})
            else:
                # User has subscription, return all questions
                if question_limit:
                    individual_questions = individual_questions[:question_limit]
                response_content = {"success": True, "homework": individual_questions, "profile": client_profile, "mode": "tutor"}
                resp = JSONResponse(content=response_content)
                if new_anon_session_id:
                    resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
                return resp
        else:  # Default to homework mode
            all_homework_results = limit_homework_question_count(
                all_homework_results,
                question_limit,
            )
            response_content = {"success": True, "homework": all_homework_results, "profile": client_profile, "mode": "homework"}
            resp = JSONResponse(content=response_content)
            if new_anon_session_id:
                resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
            return resp
    except Exception as exc:
        logger.error("Error generating homework: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.post("/api/review")
async def api_review(req: Request, request_body: ReviewRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)
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
        free_rag_tutor_review = bool(
            request_body.is_tutor_mode
            and request_body.from_rag
            and request_body.homework_doc_id
        )
        if not uses_quick_model and not free_rag_tutor_review:
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
                feature = (
                    "Review Question"
                    if request_body.is_tutor_mode
                    else "11+ year-round review"
                    if is_year_round_review
                    else "Detailed review"
                )
                return _subscription_required_response(
                    feature, required_plan, logged_in_username
                )

        result = await run_blocking(
            review_homework,
            request_body.homework,
            request_body.answers,
            request_body.subject,
            profile,
            quick_review=bool(request_body.quick_review),
            is_tutor_mode=bool(request_body.is_tutor_mode),
            homework_doc_id=request_body.homework_doc_id,
            is_eleven_plus=bool(request_body.is_eleven_plus),
            question_index=request_body.question_index,
            timeout=120,
        )
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
        return resp
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error reviewing homework")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not check the answers just now. Please try again."},
        )


@app.post("/api/explain-deep")
async def api_explain_deep(req: Request, request_body: ExplainDeepRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)
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
                "Explain in Detail", required_plan, logged_in_username
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
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
        return resp
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in explain_deep endpoint")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "We could not make the detailed explanation just now. Please try again."},
        )


@app.post("/api/improve-practice")
async def api_improve_practice(req: Request, request_body: ImprovePracticeRequest):
    try:
        initialize()
        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)
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
                "Help me improve", required_plan, logged_in_username
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
        resp = JSONResponse(
            status_code=502 if result.get("llm_no_response") else 200,
            content=result,
        )
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
        return resp
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in improve_practice endpoint")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "The AI tutor could not generate extra practice content just now. Please try again in a moment.",
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
    """Return progress only for a learner owned by the signed-in parent."""
    try:
        resolved_student_id, logged_in_username, _ = _get_user_or_anonymous_id(req)
        if logged_in_username is None:
            return JSONResponse(status_code=401, content={"success": False, "error": "Login required to view progress."})

        target_student_id = str(student_id or resolved_student_id).strip()
        from src.webapp.account_store import ensure_account, student_belongs_to_account

        account = await run_blocking(
            ensure_account,
            logged_in_username,
            timeout=10,
            limit_concurrency=False,
        )
        belongs = await run_blocking(
            student_belongs_to_account,
            target_student_id,
            account["id"],
            timeout=10,
            limit_concurrency=False,
        )
        if not belongs:
            return JSONResponse(status_code=403, content={"success": False, "error": "Access denied to this learner's progress."})

        if not await run_blocking(
            user_has_subscription,
            req,
            target_student_id,
            logged_in_username,
            timeout=12,
            limit_concurrency=False,
        ):
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

        raw_summary, score_history, topics, daily_goal, streak, accuracy = await asyncio.gather(
            asyncio.to_thread(get_progress_summary, target_student_id),
            asyncio.to_thread(get_score_history, target_student_id, subject),
            asyncio.to_thread(get_topic_progress, target_student_id, subject),
            asyncio.to_thread(get_daily_goal_stats, target_student_id),
            asyncio.to_thread(get_streak_info, target_student_id),
            asyncio.to_thread(get_accuracy_rate, target_student_id),
        )

        total_sessions = raw_summary.get("total_sessions", 0)
        avg_accuracy_pct = round(float(raw_summary.get("average_accuracy") or 0), 1)

        by_subject = []
        for subj in raw_summary.get("subjects", []):
            by_subject.append({
                "subject": subj["subject"],
                "avg_accuracy": round(float(subj.get("avg_accuracy") or 0), 1),
                "total_sessions": subj["count"],
            })

        score_history_formatted = []
        for s in score_history:
            score_val = s.get("score", 0) or 0
            score_history_formatted.append({
                "subject": s.get("subject", ""),
                "score": score_val,
                "max_score": s.get("max_score", 10) or 10,
                "created_at": s.get("created_at", ""),
            })

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
            status_code=500,
            content={"success": False, "error": "We could not load progress just now. Please try again."},
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
    try:
        session = await asyncio.to_thread(
            tutor_session_store.update,
            session_id,
            session_owner,
            body.model_dump(exclude_unset=True),
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
async def create_subscription(request: SubscriptionRequest):
    try:
        from src.admin import subscription_duration_days

        if request.duration not in {"5_days", "1_month", "30_days"}:
            raise HTTPException(status_code=400, detail="Invalid duration")
        duration_days = subscription_duration_days(request.duration)

        product_name = (
            "5-Day Premium Access" if request.duration == "5_days" else "One-Month Premium Access"
        )

        # 开发模式：直接写入本地数据库
        if _dev_mode:
            from src.progress_db import create_local_subscription
            result = create_local_subscription(
                customer_email=request.email,
                customer_name=request.name,
                product_name=product_name,
                duration_days=duration_days,
            )
            return {
                "success": True,
                "subscription_id": result["subscription_id"],
                "customer_id": "dev_customer",
                "product_name": product_name,
                "description": f"Dev mode: {product_name}",
                "duration": request.duration,
            }

        # Production checkout is owned by Stripe's hosted Pricing Table. This
        # legacy endpoint must never create a subscription from browser-supplied
        # email/name values or placeholder Price IDs.
        raise HTTPException(
            status_code=410,
            detail="Use the secure Stripe Pricing Table on /pricing.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating subscription: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.get("/api/check-subscription")
async def check_subscription_api(req: Request, plan: Optional[str] = None):
    """API endpoint to check subscription status for the current user (logged in or anonymous)."""
    resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

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

    response_content = {
        "has_subscription": has_sub,
        "student_id": resolved_student_id,
        "logged_in": logged_in_username is not None,
        "required_plan": required_plan,
        "required_plan_name": PREMIUM_PLAN_NAMES.get(required_plan) if required_plan else None,
    }
    resp = JSONResponse(content=response_content)
    if new_anon_session_id:
        resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
    return resp


@app.post("/api/register")
async def api_register(request: AuthRequest):
    try:
        from src.progress_db import create_user
        from src.auth_tokens import generate_token
        # Basic validation
        username = request.get_username()
        password = request.password

        if not username:
            return JSONResponse(status_code=400, content={"success": False, "error": "Email address is required"})
        if not password:
            return JSONResponse(status_code=400, content={"success": False, "error": "Password is required"})
        if len(password) < 8:
            return JSONResponse(status_code=400, content={"success": False, "error": "Password must be at least 8 characters long"})

        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, username):
            return JSONResponse(status_code=400, content={"success": False, "error": "Please enter a valid email address"})

        try:
            create_user(username, password)
        except ValueError as ve:
            error_msg = str(ve)
            if "already exists" in error_msg.lower():
                return JSONResponse(status_code=400, content={"success": False, "error": "This email is already registered. Please login or use a different email."})
            return JSONResponse(status_code=400, content={"success": False, "error": error_msg})

        # Set session cookie
        token = generate_token(username)
        resp = JSONResponse({"success": True, "username": username})
        secure_flag = not _dev_mode
        resp.set_cookie("session", token, httponly=True, samesite="lax", secure=secure_flag)
        return resp
    except Exception as exc:
        logger.error("Error in register: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": f"Registration error: {str(exc)}"})


@app.post("/api/login")
async def api_login(request: AuthRequest):
    try:
        from src.progress_db import verify_user_credentials
        from src.auth_tokens import generate_token
        username = request.get_username()
        password = request.password

        if not username:
            return JSONResponse(status_code=400, content={"success": False, "error": "Email address is required"})
        if not password:
            return JSONResponse(status_code=400, content={"success": False, "error": "Password is required"})

        ok = verify_user_credentials(username, password)
        if not ok:
            return JSONResponse(status_code=401, content={"success": False, "error": "Invalid email or password. Please check your credentials and try again."})

        token = generate_token(username)
        resp = JSONResponse({"success": True, "username": username})
        secure_flag = not _dev_mode
        resp.set_cookie("session", token, httponly=True, samesite="lax", secure=secure_flag)
        return resp
    except Exception as exc:
        logger.error("Error in login: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": f"Login error: {str(exc)}"})


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"success": True})
    resp.delete_cookie("session")
    return resp


@app.post("/api/upload-file")
async def upload_file(request: Request, file: UploadFile = File(...)):
    try:
        initialize()

        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")

        allowed_all = (
                ALLOWED_IMAGE_EXTENSIONS | ALLOWED_TEXT_EXTENSIONS | ALLOWED_PDF_EXTENSION
        )
        if not allowed_file(file.filename, allowed_all):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported file type. Please upload .jpg, .jpeg, .png, "
                    ".heic, .gif, .txt, .md, .csv, or .pdf files."
                ),
            )

        raw = await file.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large (max 16 MB)")

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        with open(filepath, "wb") as handle:
            handle.write(raw)

        # 放到线程池执行，避免阻塞事件循环
        content, is_image = await asyncio.to_thread(process_uploaded_file, filepath)
        return {"success": True, "content": content, "is_image": is_image}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error uploading file: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/upload-photo")
async def upload_photo(request: Request, request_body: PhotoRequest):
    try:
        initialize()

        if not request_body.photo:
            raise HTTPException(status_code=400, detail="No photo data")

        # 放到线程池执行，避免阻塞事件循环
        content = await asyncio.to_thread(process_base64_image, request_body.photo)
        return {"success": True, "content": content}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error uploading photo: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    """管理员手动创建订阅"""
    from src.admin import create_admin_subscription
    if not request.email or not request.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if request.duration not in ("5_days", "1_month", "30_days"):
        raise HTTPException(status_code=400, detail="Duration must be '5_days' or '1_month'")
    if request.plan not in {HOMEWORK_PREMIUM_PLAN, ELEVENPLUS_PREMIUM_PLAN}:
        raise HTTPException(status_code=400, detail="Please choose a valid premium plan")
    try:
        result = create_admin_subscription(
            email=request.email.strip(),
            name=request.name.strip(),
            duration=request.duration,
            plan=request.plan,
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
    uvicorn.run("web_app:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
