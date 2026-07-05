#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Homework Magic - Complete Web Application

FastAPI web application for SEO landing pages, the AI tutor UI, and REST APIs.
已移除 LangChain 依赖，使用轻量级 LLMClient 和缓存。
"""

import os
import sys
import logging
import base64
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

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


def generate_homework_with_profile(profile: dict, subjects: list):
    from src.homework_generator import generate_homework_for_subject

    if not profile.get("student_id"):
        profile["student_id"] = f"student_{profile.get('year_group', 3)}_default"

    results = []
    for subject in subjects:
        try:
            homework_content, doc_id = generate_homework_for_subject(profile, subject, llm)
            results.append(
                {"subject": subject, "content": homework_content, "doc_id": doc_id}
            )
            logger.info(
                "Generated homework for %s (student %s)", subject, profile["student_id"]
            )
        except Exception as exc:
            logger.error("Error generating %s: %s", subject, exc)
            results.append(
                {
                    "subject": subject,
                    "content": f"Error generating homework: {exc}",
                    "doc_id": None,
                }
            )

    return results


def review_homework(homework_content: str, student_answers: str, subject: str, profile=None):
    """批改作业 - 使用 REVIEW_HOMEWORK_PROMPT 生成简洁答案和基本解释"""
    from src.llm_client import format_prompt, build_messages
    from src.prompts import REVIEW_HOMEWORK_PROMPT
    from src.cache import review_cache, make_cache_key

    if profile is None:
        profile = {"year_group": 3, "age": 7}

    # 检查缓存
    cache_key = make_cache_key("review", subject, str(profile.get("year_group", 3)),
                               homework_content[:200], student_answers[:200])
    cached = review_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中批改缓存")
        return {"success": True, "review": cached, "from_cache": True}

    try:
        prompt_text = format_prompt(
            REVIEW_HOMEWORK_PROMPT,
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

        # 保存进度到数据库
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

        return {"success": True, "review": result}
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
    return FileResponse(path)


class ProfileRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    subjects: list = Field(default_factory=list)
    quick_select: bool = False
    year: Optional[int] = None
    student_id: Optional[str] = None


class ReviewRequest(BaseModel):
    homework: str
    answers: str
    subject: str = "Maths"
    profile: Optional[dict] = None
    session_id: Optional[str] = None


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


@app.get("/pricing")
async def pricing():
    return _static_page("static", "pricing.html")


@app.get("/app")
async def app_page():
    return _static_page("templates", "app.html")


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


# --- API endpoints ---


@app.get("/api/health")
async def health():
    return {"status": "ok", "initialized": initialized}


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
async def api_generate(request: ProfileRequest):
    try:
        initialize()

        profile = resolve_profile(
            request.profile,
            quick_select=request.quick_select,
            year=request.year,
            student_id=request.student_id
            or request.profile.get("student_id"),
        )
        subjects = request.subjects
        if not subjects:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No subjects selected"},
            )

        results = generate_homework_with_profile(profile, subjects)

        return {"success": True, "homework": results, "profile": profile}
    except Exception as exc:
        logger.error("Error generating homework: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.post("/api/review")
async def api_review(request: ReviewRequest):
    try:
        initialize()

        profile = request.profile
        if request.session_id and request.session_id in tutor_sessions:
            session = tutor_sessions[request.session_id]
            profile = profile or session.get("profile")

        result = review_homework(
            request.homework, request.answers, request.subject, profile
        )
        return result
    except Exception as exc:
        logger.error("Error reviewing homework: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.post("/api/explain-deep")
async def api_explain_deep(request: ExplainDeepRequest):
    try:
        initialize()

        result = explain_deep(
            request.homework, request.answers, request.subject,
            request.profile, request.review_feedback
        )
        return result
    except Exception as exc:
        logger.error("Error in explain_deep endpoint: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.post("/api/improve-practice")
async def api_improve_practice(request: ImprovePracticeRequest):
    try:
        initialize()

        result = improve_practice(
            request.homework, request.answers, request.subject,
            request.profile, request.review_feedback
        )
        return result
    except Exception as exc:
        logger.error("Error in improve_practice endpoint: %s", exc)
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )


@app.get("/api/progress/{student_id}")
async def api_get_progress(student_id: str, subject: Optional[str] = None):
    """获取学生的学习进度汇总数据"""
    try:
        from src.progress_db import get_progress_summary, get_score_history, get_topic_progress
        return {
            "success": True,
            "summary": get_progress_summary(student_id),
            "score_history": get_score_history(student_id, subject),
            "topics": get_topic_progress(student_id, subject),
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


@app.post("/api/upload-file")
async def upload_file(file: UploadFile = File(...)):
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
async def upload_photo(request: PhotoRequest):
    try:
        initialize()

        if not request.photo:
            raise HTTPException(status_code=400, detail="No photo data")

        content = process_base64_image(request.photo)
        return {"success": True, "content": content}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error uploading photo: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
