import os
import sys

# 加载 .env 环境变量（必须在其他 import 之前）
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import logging
import base64
import re
import json # Added: Import the json module
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, status  # Added Request and status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from passlib.context import CryptContext  # For password hashing

from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image
from src.progress_db import set_user_test_flag, is_user_test, get_user_by_username


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
tutor_sessions: Dict[str, Dict[str, Any]] = {}

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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


def user_has_subscription(req: Optional[Request] = None, student_id: Optional[str] = None, username: Optional[str] = None) -> bool:
    """Check for any active subscription for a given student_id/username.
    If req provided, it will attempt to resolve student_id/username from the request.
    """
    # If student_id/username not provided, try to resolve from request
    if req and (student_id is None or username is None):
        resolved_student_id, resolved_username, _ = _get_user_or_anonymous_id(req)
        student_id = student_id or resolved_student_id
        username = username or resolved_username

    if student_id is None and username is None:
        return False

    try:
        # Check if user is a test user (requires username)
        if username:
            from src.progress_db import is_user_test
            if is_user_test(username):
                return True
        
        # Anonymous IDs cannot have subscriptions
        if student_id and student_id.startswith("anon_"):
            return False

        if _dev_mode:
            from src.progress_db import list_local_subscriptions
            if student_id:
                subs = list_local_subscriptions(student_id=student_id)
                for s in subs:
                    if s.get("status") == "active":
                        return True
            return False
        else:
            # In production, fetch Stripe subscriptions for the specific customer
            if student_id:
                from src.progress_db import get_student_detail
                student_detail = get_student_detail(student_id)
                if student_detail and student_detail.get("stripe_customer_id"):
                    import stripe
                    subs = stripe.Subscription.list(customer=student_detail["stripe_customer_id"], status="active", limit=1)
                    return bool(subs.data)
            import stripe
            # Fallback for cases where student_id is not linked to Stripe customer
            # For now, if no student_id or no stripe_customer_id, assume no subscription.
            return False
    except Exception as e:
        logger.warning("Subscription check failed: %s", e)
        return False


app = FastAPI(
    title="Homework Magic",
    description="AI Tutor for UK Primary Schools",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _get_user_or_anonymous_id(req: Request) -> tuple[str, Optional[str], Optional[str]]:
    """
    Determines the student_id and username for the current request.
    Returns (student_id, username_if_logged_in, new_anonymous_session_id_to_set_in_cookie).
    new_anonymous_session_id_to_set_in_cookie will be None if no new cookie is needed.
    """
    from src.auth_tokens import verify_token  # Moved to top-level import
    # 1. Check for logged-in user
    token = req.cookies.get("session") or req.headers.get("Authorization") or req.headers.get("X-User-Id")
    if token:
        username = verify_token(token)
        if username:
            user_info = get_user_by_username(username) # Assuming username is email
            if user_info and user_info.get("student_id"):
                return user_info["student_id"], username, None

    # 2. Check for anonymous session ID cookie
    anonymous_session_id = req.cookies.get("anon_session_id")
    if anonymous_session_id:
        return anonymous_session_id, None, None # No username for anonymous

    # 3. Generate a new anonymous session ID
    new_anon_session_id = f"anon_{uuid.uuid4().hex}" # Prefix to distinguish from real student_ids
    return new_anon_session_id, None, new_anon_session_id


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
    questions = []
    # Split by common numbering patterns or bullet points
    # This regex tries to capture:
    # 1. Number followed by a dot (e.g., "1. Question text")
    # 2. Number in parentheses (e.g., "(1) Question text")
    # 3. Bullet points (e.g., "- Question text" or "* Question text")
    # It also handles multi-line questions by looking for the next pattern.

    # First, try to split by numbered questions (1., 2., etc.)
    # This pattern looks for a number followed by a dot and a space, at the beginning of a line.
    # It captures the number and the rest of the question text until the next number or end of string.
    numbered_questions = re.split(r'\n\s*(\d+\.\s)', homework_content)

    # The first element might be empty or a header before the first question
    if numbered_questions and not numbered_questions[0].strip():
        numbered_questions = numbered_questions[1:]  # Remove empty string at the beginning

    i = 0
    while i < len(numbered_questions):
        if re.match(r'\d+\.\s', numbered_questions[i]):  # If it's a number and a dot
            question_number = numbered_questions[i].strip()
            question_text = numbered_questions[i + 1].strip() if i + 1 < len(numbered_questions) else ""
            questions.append({
                "subject": subject,
                "content": f"{question_number}{question_text}",
                "original_full_content": homework_content  # Keep full content for context if needed
            })
            i += 2
        else:  # If it's not a numbered question, treat it as part of the previous or a standalone block
            # This handles cases where the first part is a header or unnumbered intro
            if numbered_questions[i].strip():
                questions.append({
                    "subject": subject,
                    "content": numbered_questions[i].strip(),
                    "original_full_content": homework_content
                })
            i += 1

    # If no numbered questions were found, try splitting by bullet points or just treat as one block
    if not questions:
        bullet_questions = re.split(r'\n\s*([-*]\s)', homework_content)
        if len(bullet_questions) > 1:
            # The first element might be a header or empty
            if bullet_questions[0].strip():
                questions.append({
                    "subject": subject,
                    "content": bullet_questions[0].strip(),
                    "original_full_content": homework_content
                })
            for i in range(1, len(bullet_questions), 2):
                if i + 1 < len(bullet_questions):
                    questions.append({
                        "subject": subject,
                        "content": f"{bullet_questions[i]}{bullet_questions[i + 1].strip()}",
                        "original_full_content": homework_content
                    })
        else:
            # If still no clear split, treat the whole content as one question
            questions.append({
                "subject": subject,
                "content": homework_content.strip(),
                "original_full_content": homework_content
            })

    # Filter out any empty content questions that might arise from splitting
    questions = [q for q in questions if q["content"].strip()]

    # Assign unique IDs to each question
    for i, q in enumerate(questions):
        q["question_id"] = f"{subject}_{uuid.uuid4().hex[:8]}_{i + 1}"

    return questions


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
        if homework_doc_id:
            try:
                if is_eleven_plus:
                    from src.elevenplus.elevenplus_rag import search_homework_answers as _search_answers
                else:
                    from src.homework_rag import search_homework_answers as _search_answers
                rag_answers = _search_answers(homework_doc_id)
                if rag_answers:
                    logger.info("[RAG] 找到 doc_id=%s 的正确答案，跳过 LLM 调用", homework_doc_id)
            except Exception as e:
                logger.warning("[RAG] 获取正确答案失败: %s", e)

        # 2. 如果有 RAG 答案，直接对比学生答案生成简洁批改
        if rag_answers:
            # 将正确答案和学生答案一起发给 LLM 做简洁对比
            correct_answers_text = json.dumps(rag_answers, ensure_ascii=False) if isinstance(rag_answers, (list, dict)) else str(rag_answers)
            prompt_text = format_prompt(
                prompt_template,
                student_profile=str(profile),
                subject=subject,
                day=datetime.now().strftime("%A, %B %d, %Y"),
                homework_content=homework_content,
                student_answer=student_answers,
            )
            # 在 prompt 中注入正确答案供 LLM 对比
            prompt_text += f"\n\n## 正确答案（供参考，请直接对比批改）\n{correct_answers_text}"
            messages = build_messages(prompt_text)
            result = llm.complete(messages)
        else:
            # 3. RAG 中没有答案，完全由 LLM 生成
            logger.info("[Review] RAG 中无正确答案，使用 LLM 生成批改 (doc_id=%s)", homework_doc_id)
            prompt_text = format_prompt(
                prompt_template,
                student_profile=str(profile),
                subject=subject,
                day=datetime.now().strftime("%A, %B %d, %Y"),
                homework_content=homework_content,
                student_answer=student_answers,
            )
            messages = build_messages(prompt_text)
            result = llm.complete(messages)

        # 写入缓存
        review_cache.set(cache_key, result)

        # 保存进度到数据库 (Only save for full homework sessions, not individual tutor questions)
        if not is_tutor_mode:
            try:
                from src.progress_db import save_homework_session
                # 从 review 文本中提取分数（如 "Score: 7/10" 或 "7/10"）
                score_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+)", result)
                score = float(score_match.group(1)) if score_match else None

                student_id = profile.get("student_id", "anonymous")
                save_homework_session(
                    student_id=student_id,
                    subject=subject,
                    year_group=profile.get("year_group", 3),
                    homework_content=homework_content,
                    student_answers=student_answers,
                    score=score,
                    review_text=result,
                )
            except Exception as db_exc:
                logger.warning("Failed to save progress: %s", db_exc)

        return {"success": True, "review": result, "from_rag_answers": rag_answers is not None}
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


class ExplainDeepRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    review_feedback: Optional[str] = None


class ImprovePracticeRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    review_feedback: Optional[str] = None


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
    """Get a unique client ID based on IP address for anonymous users."""
    # Get client IP - handle proxy headers
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    # Generate a stable ID from IP
    import hashlib
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12]
    anon_id = f"anon_{ip_hash}"

    return {"client_id": anon_id, "ip": client_ip}


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
                parsed = parse_profile_from_natural_language(description, llm)
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

        # Generate homework for all subjects
        all_homework_results = generate_homework_with_profile(profile, subjects, is_eleven_plus=request.is_eleven_plus)

        if request.mode == "tutor":
            individual_questions = []
            for hw_block in all_homework_results:
                # Split each subject's homework content into individual questions
                split_questions = _split_homework_into_questions(hw_block["content"], hw_block["subject"])
                # Preserve RAG metadata on each split question
                for q in split_questions:
                    q["doc_id"] = hw_block.get("doc_id")
                    q["from_rag"] = bool(hw_block.get("from_rag", False))
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
                response_content = {"success": True, "homework": individual_questions, "profile": profile, "mode": "tutor"}
                resp = JSONResponse(content=response_content)
                if new_anon_session_id:
                    resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
                return resp
        else:  # Default to homework mode
            response_content = {"success": True, "homework": all_homework_results, "profile": profile, "mode": "homework"}
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

        # Ensure profile has the resolved student_id
        profile = request_body.profile or {}
        profile["student_id"] = resolved_student_id

        # If this is a tutor-mode review and the question is not from RAG, require subscription
        if request_body.is_tutor_mode and not request_body.from_rag:
            has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
            if not has_sub:
                if logged_in_username is None:
                    return JSONResponse(status_code=401,
                                        content={"success": False, "error": "Login required to use tutor mode review for AI-generated questions."})
                return JSONResponse(status_code=402,
                                    content={"success": False, "error": "Tutor mode review for AI-generated questions requires an active subscription."})

        if request_body.session_id and request_body.session_id in tutor_sessions:
            session = tutor_sessions[request_body.session_id]
            session_profile = session.get("profile", {})
            profile = {**session_profile, **profile} # Merge, request_body.profile takes precedence

        result = review_homework(
            request_body.homework, request_body.answers, request_body.subject, profile,
            is_tutor_mode=request_body.is_tutor_mode,
            homework_doc_id=request_body.homework_doc_id,
        )
        
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
        return resp
    except Exception as exc:
        logger.error("Error reviewing homework: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.post("/api/explain-deep")
async def api_explain_deep(req: Request, request_body: ExplainDeepRequest):
    try:
        initialize()

        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        # ExplainDeep is a paid feature - require login and active subscription
        has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
        if not has_sub:
            if logged_in_username is None:
                return JSONResponse(status_code=401,
                                    content={"success": False, "error": "Login required to use Explain in Detail."})
            return JSONResponse(status_code=402, content={"success": False,
                                                          "error": "Explain in Detail requires an active subscription."})

        profile = request_body.profile or {}
        profile["student_id"] = resolved_student_id # Ensure profile has the resolved student_id

        result = explain_deep(
            request_body.homework, request_body.answers, request_body.subject,
            profile, request_body.review_feedback
        )
        
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
        return resp
    except Exception as exc:
        logger.error("Error in explain_deep endpoint: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.post("/api/improve-practice")
async def api_improve_practice(req: Request, request_body: ImprovePracticeRequest):
    try:
        initialize()

        resolved_student_id, logged_in_username, new_anon_session_id = _get_user_or_anonymous_id(req)

        # ImprovePractice is a paid feature - require login and active subscription
        has_sub = user_has_subscription(req=req, student_id=resolved_student_id, username=logged_in_username)
        if not has_sub:
            if logged_in_username is None:
                return JSONResponse(status_code=401,
                                    content={"success": False, "error": "Login required to use Help me improve."})
            return JSONResponse(status_code=402,
                                content={"success": False, "error": "Help me improve requires an active subscription."})

        profile = request_body.profile or {}
        profile["student_id"] = resolved_student_id # Ensure profile has the resolved student_id

        result = improve_practice(
            request_body.homework, request_body.answers, request_body.subject,
            profile, request_body.review_feedback
        )
        
        resp = JSONResponse(content=result)
        if new_anon_session_id:
            resp.set_cookie("anon_session_id", new_anon_session_id, httponly=True, samesite="lax", secure=not _dev_mode, max_age=365 * 24 * 60 * 60)
        return resp
    except Exception as exc:
        logger.error("Error in improve_practice endpoint: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.get("/api/progress/{student_id}")
async def api_get_progress(req: Request, student_id: str, subject: Optional[str] = None):
    """Get summary progress data for a student (daily goals, accuracy, streaks, encouraging feedback)."""
    # Progress tracking is a paid feature - require login and active subscription
    try:
        resolved_student_id, logged_in_username, _ = _get_user_or_anonymous_id(req)

        if logged_in_username is None: # Not logged in
            return JSONResponse(status_code=401, content={"success": False, "error": "Login required to view progress."})
        
        # Ensure the requested student_id matches the logged-in user's student_id
        # This prevents one user from viewing another's progress.
        user_info = get_user_by_username(logged_in_username)
        if not user_info or user_info.get("student_id") != student_id:
            return JSONResponse(status_code=403, content={"success": False, "error": "Access denied to this student's progress."})

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
        raw_summary = get_progress_summary(student_id)
        score_history = get_score_history(student_id, subject)
        topics = get_topic_progress(student_id, subject)

        # 新增指标
        daily_goal = get_daily_goal_stats(student_id)
        streak = get_streak_info(student_id)
        accuracy = get_accuracy_rate(student_id)

        # 转换为前端期望的格式
        total_sessions = raw_summary.get("total_sessions", 0)
        avg_score = raw_summary.get("average_score")
        avg_accuracy_pct = round(avg_score * 10, 1) if avg_score else 0

        # 转换科目数据
        by_subject = []
        for subj in raw_summary.get("subjects", []):
            by_subject.append({
                "subject": subj["subject"],
                "avg_accuracy": round(subj["avg_score"] * 10, 1) if subj.get("avg_score") else 0,
                "total_sessions": subj["count"],
            })

        # 转换分数历史
        score_history_formatted = []
        for s in score_history:
            score_val = s.get("score", 0) or 0
            score_history_formatted.append({
                "subject": s.get("subject", ""),
                "score": score_val,
                "max_score": 10,
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
            status_code=500, content={"success": False, "error": str(exc)}
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


@app.post("/api/sessions")
async def create_session():
    """Create a tutoring session (replaces Gradio gr.State)."""
    session_id = str(uuid.uuid4())
    tutor_sessions[session_id] = {
        "homework": [],
        "profile": {},
        "student_answers": "",
        "doc_id": "",
        "year_group": 3,
        "subject": "Maths",
        "created_at": datetime.utcnow().isoformat(),
    }
    return {"success": True, "session_id": session_id}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = tutor_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@app.put("/api/sessions/{session_id}")
async def update_session(session_id: str, request: SessionUpdateRequest):
    if session_id not in tutor_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = tutor_sessions[session_id]
    updates = request.model_dump(exclude_unset=True)
    session.update(updates)
    session["updated_at"] = datetime.utcnow().isoformat()
    return {"success": True, "session": session}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    if session_id not in tutor_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del tutor_sessions[session_id]
    return {"success": True}


@app.post("/api/create-subscription")
async def create_subscription(request: SubscriptionRequest):
    try:
        duration_days = {"5_days": 5, "30_days": 30}
        if request.duration not in duration_days:
            raise HTTPException(status_code=400, detail="Invalid duration")

        product_name = (
            "5-Day Premium Access" if request.duration == "5_days" else "30-Day Premium Access"
        )

        # 开发模式：直接写入本地数据库
        if _dev_mode:
            from src.progress_db import create_local_subscription
            result = create_local_subscription(
                customer_email=request.email,
                customer_name=request.name,
                product_name=product_name,
                duration_days=duration_days[request.duration],
            )
            return {
                "success": True,
                "subscription_id": result["subscription_id"],
                "customer_id": "dev_customer",
                "product_name": product_name,
                "description": f"Dev mode: {product_name}",
                "duration": request.duration,
            }

        # 生产模式：通过 Stripe 创建
        import stripe
        customer = stripe.Customer.create(
            email=request.email,
            name=request.name,
        )

        if request.duration == "5_days":
            plan_id = "price_5day_subscription"
            description = "Access to all premium features for 5 days"
        else:
            plan_id = "price_30day_subscription"
            description = "Access to all premium features for 30 days"

        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": plan_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )

        return {
            "success": True,
            "subscription_id": subscription.id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret,
            "customer_id": customer.id,
            "product_name": product_name,
            "description": description,
            "duration": request.duration
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating subscription: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
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

        content, is_image = process_uploaded_file(filepath)
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

        content = process_base64_image(request_body.photo)
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