"""Shared database URL and SQLAlchemy engine configuration."""
from __future__ import annotations

import os
from typing import Any, Dict


def normalise_database_url(url: str) -> str:
    """Use psycopg 3 for common platform-provided PostgreSQL URLs."""
    value = (url or "").strip()
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


def engine_options(url: str) -> Dict[str, Any]:
    options: Dict[str, Any] = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 15}
    else:
        options.update(
            pool_size=max(1, int(os.getenv("DB_POOL_SIZE", "5"))),
            max_overflow=max(0, int(os.getenv("DB_MAX_OVERFLOW", "10"))),
            pool_recycle=max(60, int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))),
            pool_timeout=max(1, int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "15"))),
        )
    return options
