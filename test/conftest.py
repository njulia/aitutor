"""Shared fixtures for isolated AI Tutor tests.

Environment variables are configured before application modules are imported.
All relational stores use one temporary SQLite database during local pytest
runs. Production still uses PostgreSQL through DATABASE_URL.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="aitutor-pytest-"))
_TEST_DATABASE_URL = os.getenv("AITUTOR_TEST_DATABASE_URL") or f"sqlite+pysqlite:///{_TEST_ROOT / 'aitutor-test.db'}"

# These must be set before importing web_app, progress_db, auth_tokens or the
# SQLAlchemy-backed webapp stores because several engines are created at import.
os.environ["DEV_MODE"] = "true"
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["ACCOUNT_DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["AUTH_DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["PROGRESS_DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["SESSION_DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["MEMORY_DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["BILLING_DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["MESSAGE_DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["APP_BASE_URL"] = "http://testserver"
os.environ["CORS_ORIGINS"] = "http://testserver"
os.environ["ADMIN_EMAILS"] = "admin@example.com"
os.environ["SESSION_OWNER_SECRET"] = "pytest-owner-secret"
os.environ["STORE_RAW_LEARNER_CONTENT"] = "false"
os.environ["STORE_RAW_AI_CONTENT"] = "false"
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["CHROMA_DB_PATH"] = str(_TEST_ROOT / "chroma")
os.environ["STRIPE_EXPECTED_LIVEMODE"] = "false"


class FakeLLM:
    """Deterministic LLM replacement used by API tests."""

    def complete(self, messages, temperature=None, max_tokens=None) -> str:
        return "Well done. Try one more example.\n\nScore: 1/1"

    def complete_json(self, messages, temperature=None, max_tokens=None):
        return {"year_group": 3, "age": 7, "extracted_subjects": ["Maths"]}


@pytest.fixture
def unique_email() -> str:
    return f"parent-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def app_module(monkeypatch):
    import web_app

    monkeypatch.setattr(web_app, "llm", FakeLLM())
    monkeypatch.setattr(web_app, "initialized", True)
    monkeypatch.setattr(web_app, "initialize", lambda: None)
    return web_app


@pytest.fixture
def client(app_module) -> Iterator[TestClient]:
    with TestClient(app_module.app, base_url="http://testserver") as test_client:
        yield test_client


def register_or_login(client: TestClient, email: str, password: str = "StrongPass123!") -> None:
    response = client.post("/api/register", json={"email": email, "password": password})
    if response.status_code == 400 and "already registered" in response.text.lower():
        response = client.post("/api/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


@pytest.fixture
def authenticated_client(client: TestClient, unique_email: str) -> TestClient:
    register_or_login(client, unique_email)
    return client


@pytest.fixture
def admin_client(client: TestClient) -> TestClient:
    register_or_login(client, "admin@example.com")
    return client
