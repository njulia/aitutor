"""Shared database URL and SQLAlchemy engine configuration.

Production modules use one process-wide engine per database URL.  Without this
registry every store creates its own SQLAlchemy pool; a single web instance can
then open dozens of Cloud SQL connections before it has done useful work.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


_ENGINES: Dict[str, Engine] = {}
_ENGINE_LOCK = threading.RLock()


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


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
            pool_size=_env_int("DB_POOL_SIZE", 3, 1, 20),
            max_overflow=_env_int("DB_MAX_OVERFLOW", 2, 0, 20),
            pool_recycle=_env_int("DB_POOL_RECYCLE_SECONDS", 1_800, 60, 7_200),
            pool_timeout=_env_int("DB_POOL_TIMEOUT_SECONDS", 10, 1, 60),
            # Reusing the newest idle connection lets old Cloud SQL
            # connections close naturally instead of keeping every slot warm.
            pool_use_lifo=True,
        )
    return options


def get_engine(url: str) -> Engine:
    """Return the shared SQLAlchemy engine for a normalised database URL."""
    normalised = normalise_database_url(url)
    if not normalised:
        raise ValueError("A database URL is required")
    engine = _ENGINES.get(normalised)
    if engine is not None:
        return engine
    with _ENGINE_LOCK:
        engine = _ENGINES.get(normalised)
        if engine is None:
            engine = create_engine(normalised, **engine_options(normalised))
            _ENGINES[normalised] = engine
        return engine
