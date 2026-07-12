"""Compatibility adapter for updating passwords in ``src.progress_db``."""
from __future__ import annotations

import contextlib
import importlib
import inspect
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable, Optional


class PasswordBackendError(RuntimeError):
    pass


def _normalise(email: str) -> str:
    return email.strip().lower()


def account_exists(email: str) -> bool:
    module = importlib.import_module("src.progress_db")
    getter = getattr(module, "get_user_by_username", None)
    if not callable(getter):
        raise PasswordBackendError("progress_db.get_user_by_username is required")
    return bool(getter(_normalise(email)))


def _call_public_updater(module: Any, email: str, password: str) -> Optional[bool]:
    for name in ("set_user_password", "update_user_password", "reset_user_password", "change_user_password"):
        func = getattr(module, name, None)
        if not callable(func):
            continue
        try:
            result = func(email, password)
        except TypeError:
            result = func(username=email, new_password=password)
        return True if result is None else bool(result)
    return None


def _hash_password(module: Any, password: str) -> str:
    for name in ("hash_password", "_hash_password"):
        func = getattr(module, name, None)
        if callable(func):
            return str(func(password))
    for name in ("pwd_context", "_pwd_context", "password_context", "PASSWORD_CONTEXT"):
        context = getattr(module, name, None)
        if context is not None and callable(getattr(context, "hash", None)):
            return str(context.hash(password))
    try:
        from passlib.context import CryptContext
        return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(password)
    except Exception as exc:
        raise PasswordBackendError("No compatible password hasher was found") from exc


def _find_connection_factory(module: Any) -> Optional[Callable]:
    for name in ("get_db_connection", "_get_connection", "get_connection", "_connect", "connect_db"):
        func = getattr(module, name, None)
        if callable(func):
            return func
    return None


def _find_sqlite_path(module: Any) -> Optional[Path]:
    env_path = os.getenv("DATABASE_PATH") or os.getenv("DB_PATH") or os.getenv("SQLITE_DB_PATH")
    if env_path:
        return Path(env_path)
    for name in ("DB_PATH", "DATABASE_PATH", "SQLITE_DB_PATH", "PROGRESS_DB_PATH"):
        value = getattr(module, name, None)
        if isinstance(value, (str, os.PathLike)):
            return Path(value)
    return None


@contextlib.contextmanager
def _connection(module: Any):
    factory = _find_connection_factory(module)
    if factory:
        candidate = factory()
        if hasattr(candidate, "__enter__"):
            with candidate as conn:
                yield conn
            return
        try:
            yield candidate
        finally:
            close = getattr(candidate, "close", None)
            if callable(close):
                close()
        return
    path = _find_sqlite_path(module)
    if not path:
        raise PasswordBackendError(
            "No password update function or SQLite database path was found in src.progress_db. "
            "Add set_user_password(username, new_password) to src.progress_db."
        )
    conn = sqlite3.connect(str(path), timeout=10)
    try:
        yield conn
    finally:
        conn.close()


def _sqlite_fallback(module: Any, email: str, password: str) -> bool:
    password_hash = _hash_password(module, password)
    with _connection(module) as conn:
        # This fallback is intentionally limited to the existing SQLite users table.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if not columns:
            raise PasswordBackendError("The users table was not found")
        email_column = next((name for name in ("username", "email", "user_email") if name in columns), None)
        password_column = next(
            (name for name in ("password_hash", "hashed_password", "password_digest", "password") if name in columns),
            None,
        )
        if not email_column or not password_column:
            raise PasswordBackendError("The users table has unsupported account columns")
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            f"UPDATE users SET {password_column} = ? WHERE lower({email_column}) = lower(?)",
            (password_hash, email),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False
        conn.commit()
    return True


def set_account_password(email: str, password: str) -> bool:
    module = importlib.import_module("src.progress_db")
    email = _normalise(email)
    public_result = _call_public_updater(module, email, password)
    if public_result is not None:
        return public_result
    return _sqlite_fallback(module, email, password)


def revoke_account_sessions(email: str) -> None:
    """Best-effort session invalidation after a password change."""
    try:
        module = importlib.import_module("src.auth_tokens")
    except Exception:
        return
    for name in ("revoke_all_for_user", "revoke_user_tokens", "revoke_all_tokens_for_user"):
        func = getattr(module, name, None)
        if callable(func):
            try:
                func(_normalise(email))
            except Exception:
                pass
            return
