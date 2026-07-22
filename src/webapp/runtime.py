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
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional, TypeVar
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse, Response

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


def production_configuration_issues() -> list[str]:
    """Return unsafe/missing production settings without exposing secret values."""
    if _env_bool("DEV_MODE", False) or _env_bool("TESTING", False):
        return []
    issues: list[str] = []
    database_url = (os.getenv("DATABASE_URL") or "").strip().lower()
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        issues.append("DATABASE_URL must use managed PostgreSQL in production")
    base_url = (os.getenv("APP_BASE_URL") or "").strip().lower()
    if not base_url.startswith("https://"):
        issues.append("APP_BASE_URL must be an HTTPS URL")
    else:
        parsed_base_url = urlparse(base_url)
        if (
            not parsed_base_url.hostname
            or parsed_base_url.path not in {"", "/"}
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            issues.append("APP_BASE_URL must be the canonical site origin without a path, query or fragment")
    origins = _csv("CORS_ORIGINS")
    if not origins or any(origin == "*" for origin in origins):
        issues.append("CORS_ORIGINS must list exact HTTPS origins")
    if not (os.getenv("ADMIN_EMAILS") or os.getenv("ADMIN_EMAIL")):
        issues.append("ADMIN_EMAILS must be configured")
    if not os.getenv("DATA_CONTROLLER_NAME", "").strip():
        issues.append("DATA_CONTROLLER_NAME must identify the legal service operator")
    if not os.getenv("PRIVACY_CONTACT_EMAIL", "").strip():
        issues.append("PRIVACY_CONTACT_EMAIL must be configured")
    if not os.getenv("PRIVACY_POSTAL_ADDRESS", "").strip():
        issues.append("PRIVACY_POSTAL_ADDRESS must be configured")
    if not os.getenv("BUSINESS_CONTACT_EMAIL", "").strip():
        issues.append("BUSINESS_CONTACT_EMAIL must be configured for customer support")
    if len(os.getenv("SESSION_OWNER_SECRET", "")) < 32:
        issues.append("SESSION_OWNER_SECRET must contain at least 32 characters")
    if (os.getenv("COOKIE_SECURE") or "").strip().lower() in {"0", "false", "no", "off"}:
        issues.append("COOKIE_SECURE cannot be disabled in production")
    if _env_bool("STORE_RAW_LEARNER_CONTENT", False):
        issues.append("STORE_RAW_LEARNER_CONTENT should remain false for child privacy")
    if _env_bool("STORE_RAW_AI_CONTENT", False):
        issues.append("STORE_RAW_AI_CONTENT should remain false for child privacy")

    from .email_service import password_reset_email_configuration_issues
    issues.extend(password_reset_email_configuration_issues())

    stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    billing_flag = os.getenv("STRIPE_BILLING_ENABLED")
    billing_enabled = (
        _env_bool("STRIPE_BILLING_ENABLED", False)
        if billing_flag is not None
        else bool(stripe_key)
    )
    if billing_enabled:
        expected_live_raw = os.getenv("STRIPE_EXPECTED_LIVEMODE")
        expected_live = (
            expected_live_raw.strip().lower() in {"1", "true", "yes", "on"}
            if expected_live_raw is not None
            else stripe_key.startswith(("sk_live_", "rk_live_"))
        )
        if not stripe_key:
            issues.append("STRIPE_SECRET_KEY must be configured when billing is enabled")
        elif expected_live and not stripe_key.startswith(("sk_live_", "rk_live_")):
            issues.append("STRIPE_SECRET_KEY must be a live key for live billing")
        elif not expected_live and not stripe_key.startswith(("sk_test_", "rk_test_")):
            issues.append("STRIPE_SECRET_KEY must be a test key when live billing is disabled")
        if not os.getenv("STRIPE_WEBHOOK_SECRET", "").strip().startswith("whsec_"):
            issues.append("STRIPE_WEBHOOK_SECRET must be configured when billing is enabled")
        stripe_price_vars = (
            "STRIPE_PRICE_TRIAL_5DAY",
            "STRIPE_PRICE_HOMEWORK_MONTHLY",
            "STRIPE_PRICE_ELEVENPLUS_MONTHLY",
        )
        stripe_prices = []
        for variable in stripe_price_vars:
            price_id = os.getenv(variable, "").strip()
            if not price_id.startswith("price_"):
                issues.append(f"{variable} must contain a Stripe Price ID")
            else:
                stripe_prices.append(price_id)
        if len(stripe_prices) != len(set(stripe_prices)):
            issues.append("Stripe plans must use different Price IDs")

    provider_aliases = {
        "vertex": "vertex_ai",
        "vertexai": "vertex_ai",
        "google_vertex_ai": "vertex_ai",
        "openai_compatible": "api",
    }
    quick_provider = (os.getenv("QUICK_REVIEW_PROVIDER") or "deepseek").strip().lower().replace("-", "_")
    detail_provider = (os.getenv("DETAIL_REVIEW_PROVIDER") or "vertex_ai").strip().lower().replace("-", "_")
    quick_provider = provider_aliases.get(quick_provider, quick_provider)
    detail_provider = provider_aliases.get(detail_provider, detail_provider)
    supported_providers = {"ollama", "api", "deepseek", "vertex_ai"}
    if quick_provider not in supported_providers:
        issues.append("QUICK_REVIEW_PROVIDER is not supported")
    if detail_provider not in supported_providers:
        issues.append("DETAIL_REVIEW_PROVIDER is not supported")
    if "deepseek" in {quick_provider, detail_provider} and not (
        os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEFAULT_API_KEY")
    ):
        issues.append("DEEPSEEK_API_KEY must be configured when using DeepSeek")
    if "vertex_ai" in {quick_provider, detail_provider}:
        if not os.getenv("GOOGLE_CLOUD_PROJECT", "").strip():
            issues.append("GOOGLE_CLOUD_PROJECT must be configured when using Vertex AI")
        if not os.getenv("GOOGLE_CLOUD_LOCATION", "").strip():
            issues.append("GOOGLE_CLOUD_LOCATION must be configured when using Vertex AI")
    return issues


def validate_production_configuration() -> None:
    issues = production_configuration_issues()
    strict = _env_bool("ENFORCE_PRODUCTION_CONFIG", True)
    if issues and strict:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(issues))
    for issue in issues:
        logger.warning("Production configuration: %s", issue)


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

    Directly calling SQLite, PGVector, OCR, Stripe or an SDK's synchronous LLM
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
    logger.exception("Unhandled application error: %s", exc)
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
        static_path = request.url.path.lower()
        if static_path.startswith("/static/"):
            # HTML files live below /static for the clean public routes to serve,
            # but their implementation URLs must never compete in search.
            if static_path.endswith((".html", ".htm")):
                response.headers["X-Robots-Tag"] = "noindex, nofollow"
                response.headers.setdefault("Cache-Control", "public, max-age=300")
            elif static_path.endswith((".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2")):
                response.headers.setdefault(
                    "Cache-Control", "public, max-age=3600, stale-while-revalidate=86400"
                )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if not settings.dev_mode:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class CanonicalHostMiddleware(BaseHTTPMiddleware):
    """Permanently consolidate the configured alternate host onto APP_BASE_URL."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _env_bool("DEV_MODE", False) or _env_bool("TESTING", False):
            return await call_next(request)

        canonical = urlparse((os.getenv("APP_BASE_URL") or "").strip())
        canonical_host = (canonical.hostname or "").lower()
        if canonical.scheme not in {"http", "https"} or not canonical_host:
            return await call_next(request)

        request_host = (request.headers.get("host") or "").split(":", 1)[0].strip().lower()
        configured_alternates = {
            value.lower() for value in _csv("CANONICAL_REDIRECT_HOSTS")
        }
        if not configured_alternates:
            configured_alternates.add(
                canonical_host[4:] if canonical_host.startswith("www.") else f"www.{canonical_host}"
            )

        forwarded_proto = (
            request.headers.get("x-forwarded-proto") or request.url.scheme
        ).split(",", 1)[0].strip().lower()
        wrong_host = request_host in configured_alternates
        wrong_scheme = request_host == canonical_host and forwarded_proto != canonical.scheme
        if not (wrong_host or wrong_scheme):
            return await call_next(request)

        raw_path = request.scope.get("raw_path") or b"/"
        path = raw_path.decode("latin-1")
        query = (request.scope.get("query_string") or b"").decode("latin-1")
        target = f"{canonical.scheme}://{canonical.netloc}{path}"
        if query:
            target += f"?{query}"
        return RedirectResponse(target, status_code=308)


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
                # Do not reveal whether an administrator account exists or is
                # logged in. Admin paths consistently fail closed with 403.
                return JSONResponse(status_code=403, content={"detail": "Admin access denied"})
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


class SensitiveRouteRateLimitMiddleware(BaseHTTPMiddleware):
    """Small per-instance abuse guard for account and support endpoints.

    Use Redis or a managed edge rate limiter when running several instances;
    this local layer is defence in depth and protects a single worker.
    """

    LIMITS = {
        "/api/login": (10, 10 * 60),
        "/api/register": (5, 60 * 60),
        "/api/password-reset/request": (5, 60 * 60),
        "/api/messages": (12, 60 * 60),
        "/api/billing/checkout": (10, 10 * 60),
    }

    def __init__(self, app: Any):
        super().__init__(app)
        self.events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        if settings.trust_proxy_headers:
            forwarded = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
            if forwarded:
                return hashlib.sha256(forwarded.encode("utf-8")).hexdigest()[:24]
        host = request.client.host if request.client else "unknown"
        return hashlib.sha256(host.encode("utf-8")).hexdigest()[:24]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _env_bool("TESTING", False):
            return await call_next(request)
        limit = self.LIMITS.get(request.url.path)
        if request.method != "POST" or not limit:
            return await call_next(request)
        maximum, window = limit
        now = time.monotonic()
        bucket = self.events[(request.url.path, self._client_key(request))]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= maximum:
            retry_after = max(1, int(window - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"success": False, "error": "Too many attempts. Please wait and try again."},
            )
        bucket.append(now)
        return await call_next(request)


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
    app.add_middleware(SensitiveRouteRateLimitMiddleware)
    app.add_middleware(AdminPathGuardMiddleware, require_admin=require_admin)
    app.add_middleware(CanonicalHostMiddleware)
