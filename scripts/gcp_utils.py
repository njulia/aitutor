#!/usr/bin/env python3
"""Create the AI Tutor PostgreSQL schema.

This project deliberately keeps table creation close to each bounded context.
Importing and initialising every store here creates all tables in one database.
Use a managed PostgreSQL backup policy before production upgrades.
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
from urllib.parse import quote_plus


load_dotenv()


def init_database_dev() -> int:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not (url.startswith("postgresql://") or url.startswith("postgresql+psycopg://")):
        print("DATABASE_URL must point to PostgreSQL", file=sys.stderr)
        return 2

    from src import auth_tokens, progress_db  # noqa: F401
    from src.webapp.account_store import init_account_db
    from src.webapp.memory_store import get_memory_store
    from src.webapp.session_store import TutorSessionStore
    from src.webapp.billing import ledger
    from src.webapp.message_routes import create_message_router

    init_account_db()
    get_memory_store()
    TutorSessionStore().initialise()
    ledger()
    create_message_router(lambda _request: ("schema-init", None, None), os.getcwd())
    print("PostgreSQL schema is ready")
    return 0


def get_database_url_dev():
    url = os.getenv("DATABASE_URL")

    print("DATABASE_URL set:", bool(url))
    print("DATABASE_URL:", url)

    if url:
        print("Driver:", url.split(":", 1)[0])
    return url


def get_database_password():
    res = quote_plus(os.environ["DB_PASSWORD"])
    print(f"GCP DB_PASSWORD: {res}")
    return res


def get_database_url() -> str:
    db_user = os.environ["DB_USER"]
    db_password = quote_plus(os.environ["DB_PASSWORD"])
    db_name = os.environ["DB_NAME"]
    connection_name = os.environ["INSTANCE_CONNECTION_NAME"]

    url = (
        f"postgresql+psycopg://{db_user}:{db_password}"
        f"@/{db_name}"
        f"?host=/cloudsql/{connection_name}"
    )
    print(f"GCP DATABASE_URL: {url}")
    return url


def main():
    get_database_url_dev()
    get_database_url()
    get_database_password()


if __name__ == "main":
    main()
