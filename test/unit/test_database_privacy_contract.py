from __future__ import annotations

from dataclasses import replace

import pytest

from src.webapp import runtime
from src.webapp.account_store import create_student, ensure_account
from src.webapp.db import normalise_database_url
from src.webapp.memory_store import LearningMemoryStore

pytestmark = pytest.mark.unit


def test_common_postgres_urls_use_psycopg3() -> None:
    assert normalise_database_url("postgres://u:p@db/app") == "postgresql+psycopg://u:p@db/app"
    assert normalise_database_url("postgresql://u:p@db/app") == "postgresql+psycopg://u:p@db/app"


def test_production_fails_closed_without_postgresql(monkeypatch) -> None:
    original = runtime.settings
    monkeypatch.setattr(runtime, "settings", replace(original, dev_mode=False))

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        runtime.validate_database_configuration()

    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///unsafe.db")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        runtime.validate_database_configuration()

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/app")
    runtime.validate_database_configuration()


def test_learner_profile_rejects_contact_or_school_information(tmp_path, monkeypatch) -> None:
    import src.webapp.account_store as account_store

    url = f"sqlite+pysqlite:///{tmp_path / 'accounts.db'}"
    monkeypatch.setenv("ACCOUNT_DATABASE_URL", url)
    if account_store._ENGINE is not None:
        account_store._ENGINE.dispose()
    monkeypatch.setattr(account_store, "_ENGINE", None)
    monkeypatch.setattr(account_store, "_ENGINE_URL", None)

    account = ensure_account("guardian@example.com")

    for unsafe_name in ("child@example.com", "Oak Road School", "SW1A postcode"):
        with pytest.raises(ValueError):
            create_student(account["id"], unsafe_name, 3, 7)


def test_learning_memory_is_off_by_default_and_stores_no_raw_answer(tmp_path) -> None:
    store = LearningMemoryStore(f"sqlite+pysqlite:///{tmp_path / 'memory.db'}")
    assert store.get_settings("stu_1", "acct_1")["enabled"] is False
    assert store.record_event(
        student_id="stu_1",
        account_id="acct_1",
        subject="Maths",
        topic="Fractions",
        outcome=0.5,
        metadata={"raw_answer": "private child answer", "question": "private question"},
    ) is False

    store.update_settings("stu_1", "acct_1", enabled=True, retention_days=90)
    assert store.record_event(
        student_id="stu_1",
        account_id="acct_1",
        subject="Maths",
        topic="Fractions",
        outcome=0.5,
        metadata={"raw_answer": "private child answer", "question": "private question", "mode": "tutor"},
    ) is True

    event = store.summary("stu_1", "acct_1")["recent_events"][0]
    assert "raw_answer" not in event
    assert "question" not in event
