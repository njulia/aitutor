"""Runtime hardening helpers for the Homework Magic FastAPI application.

The module is dependency-light and can be installed without changing endpoint
contracts.  It adds:

* explicit CORS configuration;
* request IDs and conservative browser security headers;
* a global admin guard for legacy ``/api/admin/*`` routes;
* bounded concurrency and timeouts for expensive AI/OCR routes;
* a safe helper for running synchronous functions away from the event loop.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional, TypeVar

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _csv(name: str, default: Iterable[str] = ()) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return tuple(values or default)


@dataclass(frozen=True)
class AppSettings:
    dev_mode: bool
    cors_origins: tuple[str, ...]
    max_ai_concurrency: int
    ai_queue_timeout_seconds: int
    request_timeout_seconds: int
    max_request_bytes: int
    trust_proxy_headers: bool
    session_cookie_secure: bool

    @classmethod
    def from_env(cls) -> "AppSettings":
        dev = _env_bool("DEV_MODE", False)
        default_origins = (
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ) if dev else ()
        origins = _csv("CORS_ORIGINS", default_origins)
        if not dev and not origins:
            logger.warning(
                "CORS_ORIGINS is empty in production; cross-origin browser requests will be denied."
            )
        return cls(
            dev_mode=dev,
            cors_origins=origins,
            max_ai_concurrency=_env_int("MAX_AI_CONCURRENCY", 8, 1, 64),
            ai_queue_timeout_seconds=_env_int("AI_QUEUE_TIMEOUT_SECONDS", 4, 1, 30),
            request_timeout_seconds=_env_int("AI_REQUEST_TIMEOUT_SECONDS", 90, 5, 300),
            max_request_bytes=_env_int("MAX_REQUEST_BYTES", 18 * 1024 * 1024, 1024, 64 * 1024 * 1024),
            trust_proxy_headers=_env_bool("TRUST_PROXY_HEADERS", False),
            session_cookie_secure=not dev,
        )


settings = AppSettings.from_env()
_blocking_semaphore: Optional[asyncio.Semaphore] = None


def _blocking_limit() -> asyncio.Semaphore:
    global _blocking_semaphore
    if _blocking_semaphore is None:
        _blocking_semaphore = asyncio.Semaphore(settings.max_ai_concurrency)
    return _blocking_semaphore


async def run_blocking(
    func: Callable[..., T],
    *args: Any,
    timeout: Optional[float] = None,
    limit_concurrency: bool = True,
    **kwargs: Any,
) -> T:
    """Run a synchronous callable in a worker thread with a timeout.

    Directly calling SQLite, Chroma, OCR, Stripe or an SDK's synchronous LLM
    method inside ``async def`` blocks every request sharing the event loop.
    This helper keeps those calls off the event loop and applies a bulkhead so
    a traffic spike cannot create an unbounded number of worker jobs.
    """

    async def invoke() -> T:
        return await asyncio.to_thread(func, *args, **kwargs)

    deadline = timeout or settings.request_timeout_seconds
    if not limit_concurrency:
        return await asyncio.wait_for(invoke(), timeout=deadline)

    semaphore = _blocking_limit()
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=settings.ai_queue_timeout_seconds)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail="The tutor is busy helping other learners. Please try again in a moment.",
        ) from exc

    try:
        return await asyncio.wait_for(invoke(), timeout=deadline)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="That took too long. Please try a shorter question or try again.",
        ) from exc
    finally:
        semaphore.release()


def public_error(exc: BaseException, message: str = "Something went wrong. Please try again.") -> str:
    """Log the real exception while returning a child-friendly safe message."""
    logger.exception("Unhandled application error", exc_info=exc)
    return message


def owner_key(identity: str) -> str:
    """Create a stable, non-reversible key without storing an email or raw token."""
    secret = os.getenv("SESSION_OWNER_SECRET", "").encode("utf-8")
    if not secret:
        # A per-process secret is fine in development. Production must set a
        # stable secret so multiple workers create the same key.
        secret = b"dev-only-change-me"
    return hashlib.blake2b(identity.encode("utf-8"), key=secret, digest_size=24).hexdigest()




def validate_database_configuration() -> None:
    """Require PostgreSQL for non-development deployments."""
    if settings.dev_mode:
        return
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required in production")
    if not (url.startswith("postgresql://") or url.startswith("postgresql+psycopg://")):
        raise RuntimeError("Production DATABASE_URL must use PostgreSQL with psycopg")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or secrets.token_urlsafe(12)
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(self), microphone=(), geolocation=(), payment=(self)",
        )
        # CSP is intentionally report-only until inline scripts are fully removed.
        response.headers.setdefault(
            "Content-Security-Policy-Report-Only",
            "default-src 'self'; img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        sensitive_prefixes = (
            "/api/account", "/api/students", "/api/memory", "/api/progress",
            "/api/messages", "/api/login", "/api/register", "/api/check-subscription",
        )
        if request.url.path.startswith(sensitive_prefixes):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if not settings.dev_mode:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class RequestSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                if int(raw_length) > settings.max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"success": False, "error": "That file or message is too large."},
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"success": False, "error": "Invalid request."})
        return await call_next(request)


class AdminPathGuardMiddleware(BaseHTTPMiddleware):
    """Protect old admin routes that forgot to call the route-level checker."""

    def __init__(self, app: Any, require_admin: Callable[[Request], Any]):
        super().__init__(app)
        self.require_admin = require_admin

    @staticmethod
    def _is_admin_path(path: str) -> bool:
        return (
            path == "/admin"
            or path.startswith("/admin/")
            or path.startswith("/api/admin/")
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._is_admin_path(request.url.path):
            try:
                result = self.require_admin(request)
                if isinstance(result, Awaitable):
                    await result
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            except Exception:
                logger.exception("Admin authorisation failed")
                return JSONResponse(status_code=403, content={"detail": "Admin access denied"})
        return await call_next(request)


class SameOriginWriteMiddleware(BaseHTTPMiddleware):
    """Reject browser cross-site state changes while allowing server webhooks."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in self.SAFE_METHODS or request.url.path == "/api/billing/stripe/webhook":
            return await call_next(request)
        origin = request.headers.get("origin")
        if not origin:
            # Non-browser clients commonly omit Origin; cookie SameSite still applies.
            return await call_next(request)
        expected = {str(request.base_url).rstrip("/")}
        expected.update(item.rstrip("/") for item in settings.cors_origins)
        configured = os.getenv("APP_BASE_URL", "").rstrip("/")
        if configured:
            expected.add(configured)
        if origin.rstrip("/") not in expected:
            return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked"})
        return await call_next(request)


class ExpensiveRouteBulkheadMiddleware(BaseHTTPMiddleware):
    EXPENSIVE_PATHS = {
        "/api/generate",
        "/api/review",
        "/api/explain-deep",
        "/api/improve-practice",
        "/api/upload-photo",
        "/api/upload-file",
    }

    def __init__(self, app: Any):
        super().__init__(app)
        self.semaphore = asyncio.Semaphore(settings.max_ai_concurrency)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path not in self.EXPENSIVE_PATHS:
            return await call_next(request)
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=settings.ai_queue_timeout_seconds)
        except TimeoutError:
            return JSONResponse(
                status_code=503,
                headers={"Retry-After": "3"},
                content={
                    "success": False,
                    "error": "The tutor is busy helping other learners. Please try again in a moment.",
                },
            )
        try:
            return await call_next(request)
        finally:
            self.semaphore.release()


def configure_cors(app: FastAPI) -> None:
    """Install credential-safe CORS; never combine cookies with a wildcard origin."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Key", "X-Request-ID", "X-CSRF-Token"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )


def install_hardening(app: FastAPI, require_admin: Callable[[Request], Any]) -> None:
    """Install middleware. Call once after creating the FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeMiddleware)
    app.add_middleware(ExpensiveRouteBulkheadMiddleware)
    app.add_middleware(SameOriginWriteMiddleware)
    app.add_middleware(AdminPathGuardMiddleware, require_admin=require_admin)
