#!/usr/bin/env python3
"""Apply the Homework Magic production-hardening patch to a repository checkout.

Usage:
    python /path/to/aitutor_hardening_patch/apply_hardening.py /path/to/aitutor

The script is deliberately conservative: it makes timestamped backups and
stops when a required anchor is missing instead of silently damaging a file.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, UTC
from pathlib import Path

PATCH_ROOT = Path(__file__).resolve().parent


class PatchError(RuntimeError):
    pass


def backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, target)
    print(f"backup: {target}")


def copy_replacement(relative: str, repo: Path) -> None:
    source = PATCH_ROOT / relative
    target = repo / relative
    if not source.exists():
        raise PatchError(f"Missing patch file: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    backup(target)
    shutil.copy2(source, target)
    print(f"replace: {relative}")


def insert_after_once(text: str, anchor: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if anchor not in text:
        raise PatchError(f"Could not find anchor for {label}: {anchor!r}")
    return text.replace(anchor, anchor + addition, 1)


def regex_replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL | re.MULTILINE)
    if count != 1:
        raise PatchError(f"Expected one match for {label}; found {count}")
    return updated


def patch_web_app(repo: Path) -> None:
    path = repo / "web_app.py"
    if not path.exists():
        raise PatchError("web_app.py not found")
    original = path.read_text(encoding="utf-8")
    text = original

    imports = (
        "\nfrom src.webapp.runtime import configure_cors, install_hardening, owner_key\n"
        "from src.webapp.session_store import TutorSessionStore\n"
        "from src.webapp.upload_utils import stream_upload_to_temp\n"
    )
    anchor = "from src.progress_db import set_user_test_flag, is_user_test, get_user_by_username\n"
    if anchor not in text:
        # Current branch may format the import over several lines.
        anchor = "from fastapi.middleware.cors import CORSMiddleware\n"
    text = insert_after_once(text, anchor, imports, "hardening imports")

    text = re.sub(
        r"^tutor_sessions:\s*Dict\[str,\s*Dict\[str,\s*Any\]\]\s*=\s*\{\}\s*$",
        "tutor_session_store = TutorSessionStore()",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if "tutor_session_store = TutorSessionStore()" not in text:
        raise PatchError("Could not replace the in-memory tutor_sessions dictionary")

    cors_pattern = r"app\.add_middleware\(\s*CORSMiddleware,.*?\n\)"
    text = regex_replace_once(
        text,
        cors_pattern,
        "configure_cors(app)\ninstall_hardening(app, require_admin=_require_admin)",
        "CORS and middleware",
    )

    client_endpoint = '''@app.get("/api/client-id")
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
            secure=not _dev_mode,
            max_age=365 * 24 * 60 * 60,
        )
    return response


'''
    text = regex_replace_once(
        text,
        r'@app\.get\("/api/client-id"\).*?(?=@app\.get\("/api/subjects"\))',
        client_endpoint,
        "privacy-safe client ID endpoint",
    )

    session_routes = '''def _request_session_owner(request: Request) -> tuple[str, Optional[str]]:
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


'''
    text = regex_replace_once(
        text,
        r'@app\.post\("/api/sessions"\).*?(?=@app\.post\("/api/create-subscription"\))',
        session_routes,
        "persistent session routes",
    )

    old_review_session = re.compile(
        r'\s*if request_body\.session_id and request_body\.session_id in tutor_sessions:\s*'
        r'session = tutor_sessions\[request_body\.session_id\]\s*'
        r'session_profile = session\.get\("profile", \{\}\)\s*'
        r'profile = \{\*\*session_profile, \*\*profile\}[^\n]*',
        re.MULTILINE,
    )
    replacement = '''
        if request_body.session_id:
            session_owner = owner_key(logged_in_username or resolved_student_id)
            session = await asyncio.to_thread(
                tutor_session_store.get, request_body.session_id, session_owner
            )
            if session:
                session_profile = session.get("profile", {})
                profile = {**session_profile, **profile}
'''
    text, count = old_review_session.subn(replacement, text, count=1)
    if count != 1:
        print("warning: review/session merge block was not found; inspect it manually")

    upload_endpoint = '''@app.post("/api/upload-file")
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
    except Exception:
        logger.exception("Error uploading file")
        raise HTTPException(status_code=500, detail="We could not read that file. Please try another one.")


'''
    text = regex_replace_once(
        text,
        r'@app\.post\("/api/upload-file"\).*?(?=@app\.post\("/api/upload-photo"\))',
        upload_endpoint,
        "streamed upload endpoint",
    )

    progress_replacements = {
        "raw_summary = get_progress_summary(student_id)": "raw_summary = await asyncio.to_thread(get_progress_summary, student_id)",
        "score_history = get_score_history(student_id, subject)": "score_history = await asyncio.to_thread(get_score_history, student_id, subject)",
        "topics = get_topic_progress(student_id, subject)": "topics = await asyncio.to_thread(get_topic_progress, student_id, subject)",
        "daily_goal = get_daily_goal_stats(student_id)": "daily_goal = await asyncio.to_thread(get_daily_goal_stats, student_id)",
        "streak = get_streak_info(student_id)": "streak = await asyncio.to_thread(get_streak_info, student_id)",
        "accuracy = get_accuracy_rate(student_id)": "accuracy = await asyncio.to_thread(get_accuracy_rate, student_id)",
    }
    for old, new in progress_replacements.items():
        text = text.replace(old, new)

    text = text.replace(
        'uvicorn.run("web_app:app", host="0.0.0.0", port=port, reload=True)',
        'uvicorn.run(\n        "web_app:app", host="0.0.0.0", port=port, reload=_dev_mode,\n'
        '        workers=1 if _dev_mode else int(os.getenv("WEB_CONCURRENCY", "2")),\n'
        '        proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes"),\n'
        '    )',
    )

    if text == original:
        raise PatchError("web_app.py was not changed")
    backup(path)
    path.write_text(text, encoding="utf-8")
    print("patch: web_app.py")


def patch_review_service(repo: Path) -> None:
    path = repo / "src" / "webapp" / "review_service.py"
    if not path.exists():
        print("warning: review_service.py not found; skipping prompt budgeting")
        return
    original = path.read_text(encoding="utf-8")
    text = original
    if "from .prompt_budget import budget_review_inputs" not in text:
        marker = "from .question_utils import"
        index = text.find(marker)
        if index < 0:
            raise PatchError("review_service.py import anchor not found")
        text = text[:index] + "from .prompt_budget import budget_review_inputs, compact_text\n" + text[index:]

    def add_budget(function_name: str, feedback_expression: str) -> None:
        nonlocal text
        pattern = (
            rf'(def {function_name}\(.*?\):.*?if profile is None:\s*profile = \{{"year_group": 3, "age": 7\}})'
        )
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            print(f"warning: could not inject prompt budget into {function_name}")
            return
        block = match.group(1)
        if "budget_review_inputs(" in block:
            return
        addition = f'''\n    _budget = budget_review_inputs(homework_content, student_answers, profile, {feedback_expression})
    homework_content = _budget["homework_content"]
    student_answers = _budget["student_answers"]
    profile = _budget["profile"]
'''
        text = text[:match.end()] + addition + text[match.end():]

    add_budget("review_homework", '""')
    add_budget("explain_deep", "review_feedback")
    add_budget("improve_practice", "review_feedback")
    text = text.replace(
        "correct_answers_section=correct_answers_section,",
        "correct_answers_section=compact_text(correct_answers_section, 4_000),",
    )

    if text != original:
        backup(path)
        path.write_text(text, encoding="utf-8")
        print("patch: src/webapp/review_service.py")


def patch_frontend(repo: Path) -> None:
    html_path = repo / "static" / "app.html"
    js_path = repo / "static" / "js" / "app.js"
    if html_path.exists():
        original = html_path.read_text(encoding="utf-8")
        text = original
        if "dompurify" not in text.lower():
            marked_script = re.search(r'<script[^>]+marked[^>]*></script>', text, flags=re.IGNORECASE)
            if not marked_script:
                raise PatchError("Could not find the Marked script in static/app.html")
            addition = (
                '\n    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js" '
                'integrity="sha384-placeholder-set-a-real-SRI-hash-before-production" crossorigin="anonymous"></script>'
                '\n    <script src="/static/js/safe_markdown.js"></script>'
            )
            # Remove placeholder integrity so browsers do not reject the script. README
            # tells the operator to pin/vendor and add verified SRI before production.
            addition = addition.replace(' integrity="sha384-placeholder-set-a-real-SRI-hash-before-production"', '')
            text = text[:marked_script.end()] + addition + text[marked_script.end():]
        if text != original:
            backup(html_path)
            html_path.write_text(text, encoding="utf-8")
            print("patch: static/app.html")
    else:
        print("warning: static/app.html not found")

    if js_path.exists():
        original = js_path.read_text(encoding="utf-8")
        text = original.replace("marked.parse(", "renderSafeMarkdown(")
        if text != original:
            backup(js_path)
            js_path.write_text(text, encoding="utf-8")
            print("patch: static/js/app.js")
    else:
        print("warning: static/js/app.js not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, help="Path to the aitutor repository checkout")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / "web_app.py").exists():
        parser.error(f"{repo} does not look like the aitutor repository")

    for relative in (
        "src/webapp/runtime.py",
        "src/webapp/session_store.py",
        "src/webapp/upload_utils.py",
        "src/webapp/prompt_budget.py",
        "src/webapp/account_store.py",
        "src/webapp/account_routes.py",
        "src/homework_rag.py",
        "static/js/safe_markdown.js",
    ):
        copy_replacement(relative, repo)

    patch_web_app(repo)
    patch_review_service(repo)
    patch_frontend(repo)
    print("\nPatch applied. Run: python -m compileall web_app.py src && pytest -q")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
