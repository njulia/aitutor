"""End-to-end API tests for the Tutor Mode review boundary.

These tests exercise request validation, FastAPI routing, and forwarding of the
zero-based question_index into the review service. Heavy external systems are
replaced at the application boundary, so no LLM, Stripe, or Chroma service is
required.
"""
import sys
import types

import pytest
from fastapi.testclient import TestClient

# The downloadable refactor package does not include the rest of the original
# application tree. Provide tiny import-time stubs so this API boundary test is
# self-contained. In the real project these imports resolve to the actual modules.
passlib_module = types.ModuleType("passlib")
passlib_context_module = types.ModuleType("passlib.context")
class _CryptContext:
    def __init__(self, *args, **kwargs):
        pass
passlib_context_module.CryptContext = _CryptContext
sys.modules.setdefault("passlib", passlib_module)
sys.modules.setdefault("passlib.context", passlib_context_module)

file_utils_module = types.ModuleType("src.file_utils")
file_utils_module.read_text_file = lambda path: ""
file_utils_module.read_pdf_file = lambda path: ""
file_utils_module.extract_text_from_image = lambda path: ""
sys.modules.setdefault("src.file_utils", file_utils_module)

progress_db_module = types.ModuleType("src.progress_db")
progress_db_module.set_user_test_flag = lambda *args, **kwargs: None
progress_db_module.is_user_test = lambda *args, **kwargs: False
progress_db_module.get_user_by_username = lambda *args, **kwargs: None
sys.modules.setdefault("src.progress_db", progress_db_module)

import web_app

pytestmark = pytest.mark.e2e


@pytest.fixture
def client(monkeypatch):
    captured = {}

    monkeypatch.setattr(web_app, "initialize", lambda: None)
    monkeypatch.setattr(web_app, "_get_user_or_anonymous_id", lambda request: ("anon-test", None, None))

    def fake_review(homework, answers, subject, profile, **kwargs):
        captured.update({
            "homework": homework,
            "answers": answers,
            "subject": subject,
            "profile": profile,
            **kwargs,
        })
        return {
            "success": True,
            "review": "RAG answer selected by index",
            "from_rag_answers": True,
        }

    monkeypatch.setattr(web_app, "review_homework", fake_review)

    with TestClient(web_app.app) as test_client:
        yield test_client, captured


def test_tutor_review_forwards_question_index_end_to_end(client):
    test_client, captured = client

    response = test_client.post(
        "/api/review",
        json={
            "homework": "10 - 4 = ?",
            "answers": "6",
            "subject": "Maths",
            "profile": {"year_group": 3},
            "is_tutor_mode": True,
            "from_rag": True,
            "homework_doc_id": "doc-42",
            "question_index": 4,
        },
    )

    assert response.status_code == 200
    assert response.json()["from_rag_answers"] is True
    assert captured["question_index"] == 4
    assert captured["homework_doc_id"] == "doc-42"
    assert captured["is_tutor_mode"] is True
    assert captured["profile"]["student_id"] == "anon-test"


def test_api_rejects_negative_question_index(client):
    test_client, _ = client

    response = test_client.post(
        "/api/review",
        json={
            "homework": "10 - 4 = ?",
            "answers": "6",
            "is_tutor_mode": True,
            "from_rag": True,
            "homework_doc_id": "doc-42",
            "question_index": -1,
        },
    )

    assert response.status_code == 422


def test_ai_generated_tutor_review_still_requires_access(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(web_app, "user_has_subscription", lambda **kwargs: False)

    response = test_client.post(
        "/api/review",
        json={
            "homework": "10 - 4 = ?",
            "answers": "6",
            "is_tutor_mode": True,
            "from_rag": False,
            "question_index": 0,
        },
    )

    assert response.status_code == 401
