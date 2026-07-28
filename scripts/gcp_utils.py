#!/usr/bin/env python3
"""Initialise the shared PostgreSQL schema used by Homework Magic."""
from __future__ import annotations

import os
import sys
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    """Return DATABASE_URL or build a Cloud SQL Unix-socket URL."""
    configured = (os.getenv("DATABASE_URL") or "").strip()
    if configured:
        return configured
    required = ("DB_USER", "DB_PASSWORD", "DB_NAME", "INSTANCE_CONNECTION_NAME")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing database configuration: " + ", ".join(missing)
        )
    return (
        "postgresql+psycopg://"
        f"{quote_plus(os.environ['DB_USER'])}:"
        f"{quote_plus(os.environ['DB_PASSWORD'])}"
        f"@/{quote_plus(os.environ['DB_NAME'])}"
        f"?host=/cloudsql/{quote_plus(os.environ['INSTANCE_CONNECTION_NAME'])}"
    )


def create_session_factory():
    """Create a bounded SQLAlchemy session factory without logging secrets."""
    url = get_database_url()
    engine = sqlalchemy_create_engine(
        url,
        pool_size=int(os.getenv("DB_POOL_SIZE", "3")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "2")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "15")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
        pool_pre_ping=True,
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialise_database() -> int:
    url = get_database_url()
    if not url.startswith(
        ("postgresql://", "postgresql+psycopg://", "postgres://")
    ):
        print("Database initialisation requires PostgreSQL.", file=sys.stderr)
        return 2

    from src import auth_tokens, progress_db  # noqa: F401
    from src.elevenplus_rag import get_elevenplus_rag_store
    from src.homework_rag import get_homework_rag_store
    from src.webapp.account_store import init_account_db
    from src.webapp.billing import ledger
    from src.webapp.memory_store import get_memory_store
    from src.webapp.message_routes import create_message_router
    from src.webapp.reward_store import get_reward_store
    from src.webapp.session_store import TutorSessionStore

    init_account_db()
    get_memory_store()
    TutorSessionStore().initialise()
    get_reward_store().initialise()
    ledger()
    create_message_router(
            resolve_identity=lambda _request: ("schema-init", None, None),
            require_admin=lambda _request: None,
            project_root=os.getcwd(),
    )

    get_homework_rag_store()
    get_elevenplus_rag_store()
    print("PostgreSQL and pgvector schema is ready.")
    return 0


def main() -> int:
    load_dotenv()
    try:
        return initialise_database()
    except Exception as exc:
        print(
            f"Database initialisation failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
