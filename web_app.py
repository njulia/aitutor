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
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image
from src.progress_db import set_user_test_flag, is_user_test, get_user_by_username
from src.webapp.runtime import configure_cors, install_hardening, owner_key, run_blocking, validate_database_configuration, public_error
from src.webapp.session_store import TutorSessionStore
from src.webapp.upload_utils import stream_upload_to_temp
from src.webapp.memory_store import get_memory_store, infer_topic, infer_misconception


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
    """Warm services and apply retention cleanup."""
    validate_database_configuration()
    initialize()
    try:
        await asyncio.to_thread(get_memory_store().purge_expired)
        await asyncio.to_thread(tutor_session_store.purge_expired)
    except Exception:
        logger.exception("Startup retention cleanup failed")
    yield


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
        header_token = req.headers.get("Authorization") or req.headers.get("X-User-Id")
        if header_token:
            maybe = verify_token(header_token)
            if maybe and get_user_by_username(maybe): # Check if user exists in DB
                return True
    except Exception:
        pass
    return False


def _resolve_username(req: Request) -> Optional[str]:
    """Return the authenticated account email, or None for anonymous users."""
    try:
        from src.auth_tokens import verify_token
        token = req.cookies.get("session") or req.headers.get("Authorization") or req.headers.get("X-User-Id")
        if not token:
            return None
        username = verify_token(token)
        if username and get_user_by_username(username):
            return username.strip().lower()
    except Exception:
        return None
    return None


def _require_admin(req: Request) -> str:
    username = _resolve_username(req)
    if not username or username not in _admin_email_allowlist():
        raise HTTPException(status_code=403, detail="Administrator access required")
    return username


def user_has_subscription(req: Optional[Request] = None, student_id: Optional[str] = None, username: Optional[str] = None) -> bool:
    """Check subscription at account level.

    `student_id` is accepted for backward compatibility but billing is linked to
    the authenticated parent/account email, not to an individual student.
    """
    if req and not username:
        username = _resolve_username(req)
    if not username:
        return False
    try:
        if is_user_test(username):
            return True
        from src.webapp.account_store import account_has_active_subscription
        if account_has_active_subscription(username):
            return True
        # Backward-compatible lookup while old subscriptions are migrated.
        if _dev_mode:
            from src.progress_db import get_local_subscriptions_by_email
            now = datetime.now(UTC)
            return any(
                item.get("status") == "active"
                and item.get("expires_at") is not None
                and item["expires_at"] > now
                for item in get_local_subscriptions_by_email(username)
            )
        return False
    except Exception as exc:
        logger.warning("Subscription check failed: %s", exc)
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
            profile.setdefault("year_group", 6)
            profile.setdefault("age", 11)
            profile.setdefault("student_id", "student_custom")

    if student_id:
        profile["student_id"] = student_id

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 6)}_default"

    return profile


def _get_user_or_anonymous_id(req: Request) -> tuple[str, Optional[str], Optional[str]]:
    """Return (active_student_id, account_email, new_anonymous_cookie).

    Existing accounts are migrated lazily to an account with one default
    student. A client may select another owned student with X-Student-Id.
    """
    username = _resolve_username(req)
    if username:
        from src.webapp.account_store import ensure_account, ensure_default_student, student_belongs_to_account
        account = ensure_account(username)
        default_student = ensure_default_student(account["id"])
        requested_student_id = (req.headers.get("X-Student-Id") or "").strip()
        if requested_student_id and student_belongs_to_account(requested_student_id, account["id"]):
            return requested_student_id, username, None
        return default_student["id"], username, None

    anonymous_session_id = req.cookies.get("anon_session_id")
    if anonymous_session_id:
        return anonymous_session_id, None, None
    new_anon_session_id = f"anon_{uuid.uuid4().hex}"
    return new_anon_session_id, None, new_anon_session_id


async def _add_learning_memory(profile: dict, username: Optional[str], student_id: str) -> tuple[dict, Optional[str]]:
    """Attach a small structured memory summary; never attach raw conversations."""
    if not username or student_id.startswith("anon_"):
        return profile, None
    try:
        from src.webapp.account_store import ensure_account, student_belongs_to_account
        account = await run_blocking(ensure_account, username, limit_concurrency=False)
        belongs = await run_blocking(student_belongs_to_account, student_id, account["id"], limit_concurrency=False)
        if not belongs:
            return profile, None
        context = await run_blocking(
            get_memory_store().prompt_context, student_id, account["id"], limit_concurrency=False
        )
        if context:
            existing = str(profile.get("learning_needs") or "").strip()
            profile["learning_needs"] = (existing + " " + context).strip()[:900]
        return profile, account["id"]
    except Exception:
        logger.exception("Could not load learning memory")
        return profile, None


async def _record_learning_memory(
    *,
    account_id: Optional[str],
    student_id: str,
    subject: str,
    homework: str,
    profile: dict,
    result: dict,
    source: str,
    from_rag: bool = False,
) -> bool:
    if not account_id or not result.get("success"):
        return False
    score = result.get("score")
    maximum = result.get("max_score")
    if score is None or not maximum:
        return False
    ratio = max(0.0, min(float(score) / float(maximum), 1.0))
    topic = infer_topic(subject, homework, profile.get("topic"))
    misconception = infer_misconception(result.get("review", ""), ratio)
    try:
        return await run_blocking(
            get_memory_store().record_event,
            student_id=student_id,
            account_id=account_id,
            subject=subject,
            topic=topic,
            outcome=ratio,
            attempted=int(result.get("attempted") or maximum or 1),
            correct_count=(
                int(result["correct_count"]) if result.get("correct_count") is not None else round(ratio * int(maximum))
            ),
            difficulty=profile.get("difficulty"),
            misconception_code=misconception,
            source=source,
            metadata={
                "mode": "tutor" if source == "tutor_review" else "homework",
                "from_rag": bool(from_rag),
                "year_group": int(profile.get("year_group", 6)),
            },
            limit_concurrency=False,
        )
    except Exception:
        logger.exception("Could not update structured learning memory")
        return False


def generate_homework_with_profile(profile: dict, subjects: list, is_eleven_plus: bool = False):
    """为多个科目生成作业（并行执行以降低延迟）"""
    from src.homework_generator import generate_homework_parallel

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 6)}_default"

    return generate_homework_parallel(profile, subjects, llm, is_eleven_plus=is_eleven_plus)



_MULTIPLE_CHOICE_OPTION_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?\(?([A-Ha-h])\)?[\)\].:\-](?:\*\*)?\s+(.+?)\s*$"
)
_MULTIPLE_CHOICE_QUESTION_RE = re.compile(
    r"^\s*(?:\*\*)?(?:question\s*)?(\d+)[\)\].:\-](?:\*\*)?\s+(.+?)\s*$",
    re.IGNORECASE,
)


def _clean_multiple_choice_text(value: str) -> str:
    """Remove light Markdown wrappers without changing the question wording."""
    cleaned = str(value or "").strip()
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"^\*\*(.*?)\*\*$", r"\1", cleaned)
    return cleaned.strip()


def _parse_multiple_choice_questions(content: str) -> List[Dict[str, Any]]:
    """Return structured questions only when at least two A-H options exist.

    The correct answer is deliberately not included in the API response. This
    parser only turns answer choices already visible in the question text into
    a safer, easier-to-use structure for the browser.
    """
    if not content:
        return []

    normalised = str(content).replace("\r\n", "\n").replace("\r", "\n")
    # Some model outputs place all choices on one line. Put each choice on its
    # own line before parsing, while leaving normal prose untouched.
    normalised = re.sub(
        r"(\S)\s+(?=(?:\*\*)?\(?[A-Ha-h]\)?[\)\].:]\s+)",
        r"\1\n",
        normalised,
    )

    questions: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    preface_lines: List[str] = []

    def finish_current() -> None:
        nonlocal current
        if not current:
            return
        stem = _clean_multiple_choice_text("\n".join(current.get("stem_lines", [])))
        options = current.get("options", [])
        if stem and len(options) >= 2:
            questions.append({
                "number": current.get("number") or len(questions) + 1,
                "question": stem,
                "options": options,
            })
        current = None

    for raw_line in normalised.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        question_match = _MULTIPLE_CHOICE_QUESTION_RE.match(line)
        if question_match:
            finish_current()
            current = {
                "number": int(question_match.group(1)),
                "stem_lines": [_clean_multiple_choice_text(question_match.group(2))],
                "options": [],
            }
            preface_lines = []
            continue

        option_match = _MULTIPLE_CHOICE_OPTION_RE.match(line)
        if option_match:
            if current is None:
                stem_lines = preface_lines[-4:] if preface_lines else []
                current = {
                    "number": len(questions) + 1,
                    "stem_lines": stem_lines,
                    "options": [],
                }
                preface_lines = []
            current["options"].append({
                "label": option_match.group(1).upper(),
                "text": _clean_multiple_choice_text(option_match.group(2)),
            })
            continue

        if current is not None:
            if current.get("options"):
                # Wrapped option text belongs to the previous option.
                current["options"][-1]["text"] = (
                    current["options"][-1]["text"] + " " + _clean_multiple_choice_text(line)
                ).strip()
            else:
                current["stem_lines"].append(_clean_multiple_choice_text(line))
        else:
            preface_lines.append(_clean_multiple_choice_text(line))

    finish_current()
    return questions


def _add_multiple_choice_metadata(item: Dict[str, Any], *, is_eleven_plus: bool) -> None:
    """Attach answer-choice metadata to 11+ items when choices are present."""
    if not is_eleven_plus:
        return
    questions = _parse_multiple_choice_questions(str(item.get("content") or ""))
    if not questions:
        return
    item["question_type"] = "multiple_choice"
    item["questions"] = questions
    if len(questions) == 1:
        item["question_text"] = questions[0]["question"]
        item["options"] = questions[0]["options"]


from src.webapp.question_utils import _split_homework_into_questions
from src.webapp.review_service import review_homework, explain_deep, improve_practice



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


from src.webapp.models import (
    ProfileRequest, ReviewRequest, ExplainDeepRequest, ImprovePracticeRequest,
    PhotoRequest, SessionUpdateRequest, FeedbackRequest, AdminUserCreateRequest,
    AdminSubscriptionCreateRequest, AdminUserUpdateRequest, SubscriptionRequest, AuthRequest,
)



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
async def elevenplus_year_round_plan():
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
    """Return a random cookie-backed ID without collecting or exposing an IP."""
    resolved_id, _username, new_anon_id = _get_user_or_anonymous_id(request)
    response = JSONResponse({"client_id": resolved_id})
    if new_anon_id:
        response.set_cookie(
            "anon_session_id", new_anon_id, httponly=True, samesite="lax",
            secure=not _dev_mode, max_age=24 * 60 * 60,
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

        profile = resolve_profile(
            request.profile,
            quick_select=request.quick_select,
            year=request.year,
            student_id=request.student_id,
        )
        profile, _memory_account_id = await _add_learning_memory(
            profile, logged_in_username, resolved_student_id
        )
        subjects = request.subjects

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
                parsed = await run_blocking(parse_profile_from_natural_language, description, llm)
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
        all_homework_results = await run_blocking(
            generate_homework_with_profile, profile, subjects, request.is_eleven_plus
        )
        for homework_item in all_homework_results:
            homework_item["is_eleven_plus"] = bool(request.is_eleven_plus)
            _add_multiple_choice_metadata(
                homework_item, is_eleven_plus=bool(request.is_eleven_plus)
            )

        if request.mode == "tutor":
            individual_questions = []
            for hw_block in all_homework_results:
                # Split each subject's homework content into individual questions
                split_questions = _split_homework_into_questions(hw_block["content"], hw_block["subject"])
                # Preserve RAG metadata on each split question
                for source_index, q in enumerate(split_questions):
                    q["doc_id"] = hw_block.get("doc_id")
                    q["from_rag"] = bool(hw_block.get("from_rag", False))
                    q["question_index"] = source_index
                    q["is_eleven_plus"] = bool(request.is_eleven_plus)
                    _add_multiple_choice_metadata(
                        q, is_eleven_plus=bool(request.is_eleven_plus)
                    )
                individual_questions.extend(split_questions)

            # Check subscription for tutor mode (only for non-RAG questions)
            has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
            
            if not has_sub:
                # Filter out non-RAG questions if not subscribed
                rag_only_questions = [q for q in individual_questions if q.get("from_rag")]
                if rag_only_questions:
                    response_content = {"success": True, "homework": rag_only_questions, "profile": profile, "mode": "tutor",
                                        "note": "Partial results: only RAG-sourced questions (free). Subscribe for full tutor mode."}
                    resp = JSONResponse(content=response_content)
                    if new_anon_session_id:
                        resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24 * 60 * 60)
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
                response_content = {"success": True, "homework": individual_questions, "profile": profile, "mode": "tutor"}
                resp = JSONResponse(content=response_content)
                if new_anon_session_id:
                    resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24 * 60 * 60)
                return resp
        else:  # Default to homework mode
            response_content = {"success": True, "homework": all_homework_results, "profile": profile, "mode": "homework"}
            resp = JSONResponse(content=response_content)
            if new_anon_session_id:
                resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24 * 60 * 60)
            return resp
    except Exception as exc:
        logger.error("Error generating homework: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": public_error(exc)}
        )


@app.post("/api/review")
async def api_review(req: Request, request_body: ReviewRequest):
    try:
        initialize()

        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        # Ensure profile has the resolved student_id
        profile = request_body.profile or {}
        profile["student_id"] = resolved_student_id
        profile, memory_account_id = await _add_learning_memory(
            profile, logged_in_username, resolved_student_id
        )

        # If this is a tutor-mode review and the question is not from RAG, require subscription
        if request_body.is_tutor_mode and not request_body.from_rag:
            has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
            if not has_sub:
                if logged_in_username is None:
                    return JSONResponse(status_code=401,
                                        content={"success": False, "error": "Login required to use tutor mode review for AI-generated questions."})
                return JSONResponse(status_code=402,
                                    content={"success": False, "error": "Tutor mode review for AI-generated questions requires an active subscription."})
        if request_body.session_id:
            session_owner = owner_key(logged_in_username or resolved_student_id)
            session = await run_blocking(tutor_session_store.get, request_body.session_id, session_owner, limit_concurrency=False)
            if session:
                profile = {**session.get("profile", {}), **profile}

        # 放到线程池执行，避免阻塞事件循环
        result = await run_blocking(
            review_homework,
            request_body.homework, request_body.answers, request_body.subject, profile,
            is_tutor_mode=request_body.is_tutor_mode,
            homework_doc_id=request_body.homework_doc_id,
            question_index=request_body.question_index,
            is_eleven_plus=request_body.is_eleven_plus,
            llm_client=llm,
            timeout=120.0
        )
        
        result["memory_updated"] = await _record_learning_memory(
            account_id=memory_account_id,
            student_id=resolved_student_id,
            subject=request_body.subject,
            homework=request_body.homework,
            profile=profile,
            result=result,
            source="tutor_review" if request_body.is_tutor_mode else "homework_review",
            from_rag=bool(request_body.from_rag),
        )
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24 * 60 * 60)
        return resp
    except Exception as exc:
        logger.error("Error reviewing homework: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": public_error(exc)}
        )


@app.post("/api/explain-deep")
async def api_explain_deep(req: Request, request_body: ExplainDeepRequest):
    try:
        initialize()

        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        # ExplainDeep is a paid feature - require login and active subscription (unless from free RAG resource)
        if not request_body.from_rag:
            has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
            if not has_sub:
                if logged_in_username is None:
                    return JSONResponse(status_code=401,
                                        content={"success": False, "error": "Login required to use Explain in Detail."})
                return JSONResponse(status_code=402, content={"success": False,
                                                              "error": "Explain in Detail requires an active subscription."})

        profile = request_body.profile or {}
        profile["student_id"] = resolved_student_id
        profile, _memory_account_id = await _add_learning_memory(
            profile, logged_in_username, resolved_student_id
        )

        result = await run_blocking(
            explain_deep,
            request_body.homework, request_body.answers, request_body.subject,
            profile, request_body.review_feedback, llm_client=llm,
            timeout=120.0
        )
        
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24 * 60 * 60)
        return resp
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in explain_deep endpoint: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": public_error(exc)}
        )


@app.post("/api/improve-practice")
async def api_improve_practice(req: Request, request_body: ImprovePracticeRequest):
    try:
        initialize()

        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        # ImprovePractice is a paid feature - require login and active subscription (unless from free RAG resource)
        if not request_body.from_rag:
            has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
            if not has_sub:
                if logged_in_username is None:
                    return JSONResponse(status_code=401,
                                        content={"success": False, "error": "Login required to use Help me improve."})
                return JSONResponse(status_code=402,
                                    content={"success": False, "error": "Help me improve requires an active subscription."})

        profile = request_body.profile or {}
        profile["student_id"] = resolved_student_id
        profile, _memory_account_id = await _add_learning_memory(
            profile, logged_in_username, resolved_student_id
        )

        result = await run_blocking(
            improve_practice,
            request_body.homework, request_body.answers, request_body.subject,
            profile, request_body.review_feedback, llm_client=llm,
            timeout=120.0
        )
        
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24 * 60 * 60)
        return resp
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in improve_practice endpoint: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": public_error(exc)}
        )


@app.get("/api/progress/{student_id}")
async def api_get_progress(req: Request, student_id: str, subject: Optional[str] = None):
    """Get summary progress data for a student (daily goals, accuracy, streaks, encouraging feedback)."""
    # Progress tracking is a paid feature - require login and active subscription
    try:
        resolved_student_id, logged_in_username, _ = _get_user_or_anonymous_id(req)

        if logged_in_username is None: # Not logged in
            return JSONResponse(status_code=401, content={"success": False, "error": "Login required to view progress."})
        
        # Parent accounts may own more than one learner profile.
        from src.webapp.account_store import ensure_account, student_belongs_to_account
        account = await run_blocking(ensure_account, logged_in_username, limit_concurrency=False)
        owns_student = await run_blocking(
            student_belongs_to_account, student_id, account["id"], limit_concurrency=False
        )
        if not owns_student:
            return JSONResponse(status_code=403, content={"success": False, "error": "Access denied to this learner's progress."})

        if not user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username):
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
        raw_summary = await run_blocking(get_progress_summary, student_id, limit_concurrency=False)
        score_history = await run_blocking(get_score_history, student_id, subject, limit_concurrency=False)
        topics = await run_blocking(get_topic_progress, student_id, subject, limit_concurrency=False)

        # 新增指标
        daily_goal = await run_blocking(get_daily_goal_stats, student_id, limit_concurrency=False)
        streak = await run_blocking(get_streak_info, student_id, limit_concurrency=False)
        accuracy = await run_blocking(get_accuracy_rate, student_id, limit_concurrency=False)

        # 转换为前端期望的格式
        total_sessions = raw_summary.get("total_sessions", 0)
        avg_accuracy_pct = float(raw_summary.get("average_accuracy", 0) or 0)

        # 转换科目数据
        by_subject = []
        for subj in raw_summary.get("subjects", []):
            by_subject.append({
                "subject": subj["subject"],
                "avg_accuracy": float(subj.get("avg_accuracy", 0) or 0),
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
    except Exception as exc:
        logger.error("Error getting progress: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": public_error(exc)}
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
    payload = {"homework": [], "profile": {}, "student_answers": "", "doc_id": "", "year_group": 6, "subject": "Maths"}
    session = await run_blocking(tutor_session_store.create, session_owner, payload, limit_concurrency=False)
    response = JSONResponse({"success": True, "session_id": session["session_id"]})
    if new_anon_id:
        response.set_cookie("anon_session_id", new_anon_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24*60*60)
    return response


@app.get("/api/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    owner, _ = _request_session_owner(request)
    session = await run_blocking(tutor_session_store.get, session_id, owner, limit_concurrency=False)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.put("/api/sessions/{session_id}")
async def update_session(request: Request, session_id: str, body: SessionUpdateRequest):
    owner, _ = _request_session_owner(request)
    session = await run_blocking(tutor_session_store.update, session_id, owner, body.model_dump(exclude_unset=True), limit_concurrency=False)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.delete("/api/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    owner, _ = _request_session_owner(request)
    deleted = await run_blocking(tutor_session_store.delete, session_id, owner, limit_concurrency=False)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@app.post("/api/create-subscription")
async def create_subscription_legacy():
    raise HTTPException(
        status_code=410,
        detail="This billing endpoint has been replaced by authenticated Stripe Checkout.",
    )


@app.get("/api/check-subscription")
async def check_subscription_api(req: Request):
    """API endpoint to check subscription status for the current user (logged in or anonymous)."""
    resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

    has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)

    response_content = {
        "has_subscription": has_sub,
        "student_id": resolved_student_id,
        "logged_in": logged_in_username is not None
    }
    resp = JSONResponse(content=response_content)
    if new_anon_session_id:
        resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=24 * 60 * 60)
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
        resp.set_cookie("session", token, httponly=True, samesite="lax", secure=secure_flag, max_age=12 * 60 * 60)
        return resp
    except Exception as exc:
        logger.error("Error in register: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": public_error(exc, "Registration could not be completed. Please try again.")})


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
        resp.set_cookie("session", token, httponly=True, samesite="lax", secure=secure_flag, max_age=12 * 60 * 60)
        return resp
    except Exception as exc:
        logger.error("Error in login: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": public_error(exc, "Login could not be completed. Please try again.")})


@app.post("/api/logout")
async def api_logout(request: Request):
    from src.auth_tokens import revoke_token
    token = request.cookies.get("session") or request.headers.get("Authorization")
    if token:
        await run_blocking(revoke_token, token, limit_concurrency=False)
    resp = JSONResponse({"success": True})
    resp.delete_cookie("session", httponly=True, samesite="lax", secure=not _dev_mode)
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
        raise HTTPException(status_code=500, detail=public_error(exc, "That file could not be processed.")) from exc


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
        raise HTTPException(status_code=500, detail=public_error(exc, "That file could not be processed.")) from exc


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
async def admin_page(req: Request):
    """Serve the existing admin dashboard with a messages shortcut injected."""
    _require_admin(req)
    path = os.path.join(project_root, "static", "admin.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Page not found")
    with open(path, "r", encoding="utf-8") as handle:
        html = handle.read()
    script = '<script src="/static/js/admin-message-link.js" defer></script>'
    if script not in html:
        html = html.replace("</body>", f"    {script}\n</body>")
    return HTMLResponse(html, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })


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


def _admin_email_allowlist() -> set[str]:
    """Return lowercase administrator emails configured through ADMIN_EMAILS."""
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


@app.get("/api/admin/access-status")
async def admin_access_status(req: Request):
    """Return whether the currently authenticated user is an administrator."""
    _student_id, username, _new_anon_session_id = _get_user_or_anonymous_id(req)
    is_admin = bool(username and username.strip().lower() in _admin_email_allowlist())
    return {"is_admin": is_admin}


@app.get("/api/admin/dev-mode-status")
async def admin_dev_mode_status(req: Request):
    """Backward-compatible status endpoint; never grants admin access by DEV_MODE alone."""
    _student_id, username, _new_anon_session_id = _get_user_or_anonymous_id(req)
    is_admin = bool(username and username.strip().lower() in _admin_email_allowlist())
    return {"is_dev_mode": _dev_mode, "is_admin": is_admin}


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



# Account, student and account-level subscription module
from src.webapp.account_routes import build_account_router
app.include_router(build_account_router(resolve_username=_resolve_username, require_admin=_require_admin, session_store=tutor_session_store))

# Parent-account Stripe Checkout and verified webhook billing
from src.webapp.billing import build_billing_router
app.include_router(build_billing_router(resolve_username=_resolve_username))

# Parent-controlled structured learning memory
from src.webapp.memory_routes import build_memory_router
app.include_router(build_memory_router(resolve_username=_resolve_username))

# Parent/guardian contact messages and authenticated admin replies
from src.webapp.message_routes import create_message_router
app.include_router(create_message_router(
    resolve_identity=_get_user_or_anonymous_id,
    require_admin=_require_admin,
    project_root=project_root,
))

# Secure, single-use parent/guardian password reset flow
from src.webapp.password_reset_routes import create_password_reset_router
app.include_router(create_password_reset_router(project_root=project_root, dev_mode=_dev_mode))

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
    uvicorn.run("web_app:app", host="0.0.0.0", port=port, reload=_dev_mode, workers=1 if _dev_mode else int(os.getenv("WEB_CONCURRENCY", "2")))


if __name__ == "__main__":
    main()