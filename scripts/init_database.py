#!/usr/bin/env python3
"""Create the AI Tutor PostgreSQL schema.

This project deliberately keeps table creation close to each bounded context.
Importing and initialising every store here creates all tables in one database.
Use a managed PostgreSQL backup policy before production upgrades.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
