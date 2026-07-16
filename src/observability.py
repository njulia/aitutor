"""Privacy-first Langfuse tracing helpers for Homework Magic.

The module is deliberately optional: when Langfuse is not installed or its
credentials are missing, all helpers become no-ops and application behaviour is
unchanged.

Environment variables:
    LANGFUSE_PUBLIC_KEY
    LANGFUSE_SECRET_KEY
    LANGFUSE_BASE_URL (or LANGFUSE_HOST)
    LANGFUSE_TRACING_ENABLED=true|false       (default: true)
    LANGFUSE_CAPTURE_CONTENT=true|false       (default: false)
    LANGFUSE_CAPTURE_FEEDBACK_COMMENTS=true|false (default: false)
    LANGFUSE_USER_HASH_SALT=<private random value>
    LANGFUSE_TRACING_ENVIRONMENT=development|staging|production
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import logging
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional

logger = logging.getLogger(__name__)

_TRUE = {"1", "true", "yes", "on"}
_SECRET_KEYS = {
    "authorization", "cookie", "password", "passcode", "secret", "token",
    "api_key", "apikey", "access_token", "refresh_token", "session",
}
_PII_KEYS = {
    "email", "name", "username", "student_name", "parent_name", "address",
    "phone", "photo", "image", "file", "document", "homework", "answers",
    "answer", "content", "prompt", "messages", "description", "review",
    "explanation", "practice", "input", "output", "query", "question",
    "student",
}
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

_client: Any = None
_client_initialised = False
_PROCESS_HASH_SALT = os.urandom(32).hex()


def _env_true(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def _credentials_present() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _normalise_base_url() -> None:
    """Langfuse v4 prefers LANGFUSE_BASE_URL; keep old self-hosted setups working."""
    if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
        os.environ["LANGFUSE_BASE_URL"] = os.environ["LANGFUSE_HOST"]
    if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]


def get_langfuse_client() -> Any:
    """Return the singleton Langfuse client, or ``None`` when tracing is disabled."""
    global _client, _client_initialised
    if _client_initialised:
        return _client
    _client_initialised = True

    if not _env_true("LANGFUSE_TRACING_ENABLED", default=True):
        logger.info("Langfuse tracing is disabled by LANGFUSE_TRACING_ENABLED")
        return None
    if not _credentials_present():
        logger.info("Langfuse credentials are not configured; tracing is disabled")
        return None

    _normalise_base_url()
    try:
        # Import only after .env has been loaded by the application entrypoint.
        from langfuse import get_client

        _client = get_client()
        logger.info("Langfuse tracing initialised")
    except Exception:
        logger.exception("Langfuse could not be initialised; continuing without tracing")
        _client = None
    return _client


def langfuse_status() -> Dict[str, Any]:
    """Return non-secret diagnostic state suitable for a health/admin endpoint."""
    try:
        import langfuse  # type: ignore

        version = getattr(langfuse, "__version__", "unknown")
        installed = True
    except Exception:
        version = None
        installed = False
    return {
        "installed": installed,
        "version": version,
        "configured": _credentials_present(),
        "enabled": get_langfuse_client() is not None,
        "capture_content": _env_true("LANGFUSE_CAPTURE_CONTENT", default=False),
    }


def _hash_identifier(value: Optional[str], prefix: str) -> Optional[str]:
    if not value:
        return None
    salt = (
        os.getenv("LANGFUSE_USER_HASH_SALT")
        or os.getenv("NEXTAUTH_SECRET")
        or os.getenv("SALT")
        or _PROCESS_HASH_SALT
    )
    digest = hashlib.sha256(f"{salt}:{value}".encode("utf-8", errors="ignore")).hexdigest()
    return f"{prefix}_{digest[:32]}"


def _summarise_text(value: str) -> Any:
    text = value or ""
    if _env_true("LANGFUSE_CAPTURE_CONTENT", default=False):
        return _EMAIL_RE.sub("[redacted-email]", text)[:8_000]
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return {"type": "text", "chars": len(text), "sha256": digest}


def _key_is_sensitive(key: str) -> bool:
    folded = key.casefold().replace("-", "_")
    return folded in _SECRET_KEYS or any(part in folded for part in _SECRET_KEYS)


def _key_contains_content(key: str) -> bool:
    folded = key.casefold().replace("-", "_")
    return folded in _PII_KEYS or any(part in folded for part in _PII_KEYS)


def sanitise(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Remove secrets and summarise child/user content before it leaves the app."""
    if depth > 6:
        return "[max-depth]"
    if _key_is_sensitive(key):
        return "[redacted]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if _key_contains_content(key) or len(value) > 200:
            return _summarise_text(value)
        return _EMAIL_RE.sub("[redacted-email]", value)[:200]
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:50]:
            clean_key = str(raw_key)[:80]
            result[clean_key] = sanitise(raw_value, key=clean_key, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return [sanitise(item, key=key, depth=depth + 1) for item in items[:50]]
    if hasattr(value, "model_dump"):
        try:
            return sanitise(value.model_dump(), key=key, depth=depth + 1)
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return sanitise(value.dict(), key=key, depth=depth + 1)
        except Exception:
            pass
    return _summarise_text(str(value))


def _propagation_metadata(metadata: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """Produce Langfuse propagation-safe metadata (alphanumeric keys, short strings)."""
    result: Dict[str, str] = {}
    for key, value in (metadata or {}).items():
        clean_key = re.sub(r"[^A-Za-z0-9]", "", str(key))[:60]
        if not clean_key:
            continue
        clean_value = sanitise(value, key=str(key))
        text = str(clean_value)
        result[clean_key] = text[:200]
    return result


@dataclass
class ObservationHandle:
    observation: Any = None
    client: Any = None

    @property
    def trace_id(self) -> Optional[str]:
        if self.observation is not None:
            trace_id = getattr(self.observation, "trace_id", None)
            if trace_id:
                return str(trace_id)
        if self.client is not None:
            try:
                return self.client.get_current_trace_id()
            except Exception:
                return None
        return None

    def set_output(self, output: Any) -> None:
        if self.observation is None:
            return
        try:
            self.observation.update(output=sanitise(output, key="output"))
        except Exception:
            logger.debug("Could not update Langfuse observation output", exc_info=True)

    def set_metadata(self, metadata: Mapping[str, Any]) -> None:
        if self.observation is None:
            return
        try:
            self.observation.update(metadata=sanitise(dict(metadata), key="metadata"))
        except Exception:
            logger.debug("Could not update Langfuse observation metadata", exc_info=True)

    def set_error(self, exc: BaseException) -> None:
        if self.observation is None:
            return
        try:
            self.observation.update(
                level="ERROR",
                status_message=str(exc)[:500],
                metadata={"errorType": type(exc).__name__},
            )
        except Exception:
            logger.debug("Could not update Langfuse observation error", exc_info=True)


@contextmanager
def trace_span(
    name: str,
    *,
    as_type: str = "span",
    input_data: Any = None,
    model: Optional[str] = None,
    model_parameters: Optional[Mapping[str, Any]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Iterator[ObservationHandle]:
    """Create a nested observation, or yield a no-op handle when disabled."""
    client = get_langfuse_client()
    if client is None:
        yield ObservationHandle()
        return

    kwargs: Dict[str, Any] = {
        "as_type": as_type,
        "name": name,
        "input": sanitise(input_data, key="input"),
    }
    if model:
        kwargs["model"] = str(model)[:200]
    if model_parameters:
        kwargs["model_parameters"] = sanitise(dict(model_parameters), key="modelParameters")
    if metadata:
        kwargs["metadata"] = sanitise(dict(metadata), key="metadata")

    # Enter and exit the Langfuse context manually so telemetry failures are
    # logged and swallowed, while application exceptions are always re-raised.
    context = None
    try:
        context = client.start_as_current_observation(**kwargs)
        observation = context.__enter__()
    except Exception:
        logger.exception("Could not start Langfuse observation; continuing without tracing")
        yield ObservationHandle()
        return

    handle = ObservationHandle(observation=observation, client=client)
    try:
        yield handle
    except BaseException as exc:
        handle.set_error(exc)
        try:
            context.__exit__(type(exc), exc, exc.__traceback__)
        except Exception:
            logger.exception("Could not close failed Langfuse observation")
        raise
    else:
        try:
            context.__exit__(None, None, None)
        except Exception:
            logger.exception("Could not close Langfuse observation; application result kept")


def _feature_for_path(path: str) -> str:
    mapping = {
        "/api/generate": "homework-generation",
        "/api/review": "homework-review",
        "/api/explain-deep": "deep-explanation",
        "/api/improve-practice": "targeted-practice",
        "/api/upload-file": "homework-upload",
        "/api/upload-photo": "photo-upload",
        "/api/feedback": "user-feedback",
    }
    if path.startswith("/api/sessions"):
        return "tutor-session"
    if path.startswith("/api/progress"):
        return "progress"
    return mapping.get(path, "api")


def install_langfuse_middleware(app: Any, *, app_version: str = "unknown") -> None:
    """Add privacy-first request tracing to a FastAPI application."""
    try:
        from langfuse import propagate_attributes
        from starlette.middleware.base import BaseHTTPMiddleware
    except Exception:
        logger.info("Langfuse/FastAPI tracing middleware not installed (dependency unavailable)")
        return

    class LangfuseTracingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Any, call_next: Any) -> Any:
            path = request.url.path
            if not path.startswith("/api/") or path in {"/api/health", "/api/client-id"}:
                return await call_next(request)

            feature = _feature_for_path(path)
            raw_identity = (
                request.cookies.get("anon_session_id")
                or request.cookies.get("session")
                or request.headers.get("X-Client-Id")
            )
            raw_session = (
                request.headers.get("X-Tutor-Session-Id")
                or request.headers.get("X-Session-Id")
                or request.cookies.get("anon_session_id")
            )
            user_id = _hash_identifier(raw_identity, "user")
            session_id = _hash_identifier(raw_session, "session")
            metadata = {
                "feature": feature,
                "httpMethod": request.method,
                "httpPath": path,
                "appVersion": app_version,
                "contentLength": request.headers.get("content-length", "0"),
            }
            tags = ["homework-magic", feature, request.method.lower()]

            client = get_langfuse_client()
            if client is None:
                return await call_next(request)

            request_executed = False
            response = None
            try:
                with client.start_as_current_observation(
                    as_type="span",
                    name=feature,
                    input={
                        "method": request.method,
                        "path": path,
                        "query": sanitise(dict(request.query_params), key="query"),
                    },
                ) as root_span:
                    attributes: Dict[str, Any] = {
                        "metadata": _propagation_metadata(metadata),
                        "tags": tags,
                        "trace_name": feature,
                    }
                    if user_id:
                        attributes["user_id"] = user_id
                    if session_id:
                        attributes["session_id"] = session_id
                    environment = os.getenv("LANGFUSE_TRACING_ENVIRONMENT")
                    if environment:
                        attributes["environment"] = environment

                    with propagate_attributes(**attributes):
                        try:
                            # Mark the request as started before awaiting it. If the
                            # endpoint raises, never call it a second time.
                            request_executed = True
                            response = await call_next(request)
                        except BaseException as exc:
                            try:
                                root_span.update(
                                    level="ERROR",
                                    status_message=str(exc)[:500],
                                    output={"status": "error", "errorType": type(exc).__name__},
                                )
                            except Exception:
                                pass
                            raise

                        trace_id = getattr(root_span, "trace_id", None)
                        try:
                            root_span.update(
                                output={"statusCode": response.status_code},
                                metadata={"httpStatusCode": response.status_code},
                            )
                        except Exception:
                            pass
                        if trace_id:
                            response.headers["X-Langfuse-Trace-Id"] = str(trace_id)
                            exposed = response.headers.get("Access-Control-Expose-Headers", "")
                            exposed_names = {item.strip().lower() for item in exposed.split(",") if item.strip()}
                            if "x-langfuse-trace-id" not in exposed_names:
                                response.headers["Access-Control-Expose-Headers"] = (
                                    f"{exposed}, X-Langfuse-Trace-Id".strip(", ")
                                )
                        return response
            except Exception:
                # Tracing must never take down the tutoring application. Never
                # execute the endpoint twice if tracing fails after call_next().
                logger.exception("Langfuse request tracing failed")
                if request_executed:
                    if response is not None:
                        return response
                    raise
                return await call_next(request)

    app.add_middleware(LangfuseTracingMiddleware)


def _infer_model(client: Any) -> str:
    for name in ("model", "model_name", "model_id", "deployment_name", "_model"):
        value = getattr(client, name, None)
        if value:
            return str(value)
    for name in ("LLM_MODEL", "GEMINI_MODEL", "QWEN_MODEL", "OLLAMA_MODEL", "OPENAI_MODEL"):
        value = os.getenv(name)
        if value:
            return value
    return client.__class__.__name__


def _model_parameters(kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    keys = ("temperature", "max_tokens", "max_output_tokens", "top_p", "top_k", "seed")
    return {key: kwargs[key] for key in keys if key in kwargs and kwargs[key] is not None}


def _extract_usage(result: Any, client: Any) -> Optional[Dict[str, int]]:
    candidates = []
    if isinstance(result, Mapping):
        candidates.extend([result.get("usage"), result.get("usage_metadata")])
    else:
        candidates.extend([getattr(result, "usage", None), getattr(result, "usage_metadata", None)])
    candidates.append(getattr(client, "last_usage", None))

    for candidate in candidates:
        if candidate is None:
            continue
        if hasattr(candidate, "model_dump"):
            try:
                candidate = candidate.model_dump()
            except Exception:
                continue
        elif not isinstance(candidate, Mapping) and hasattr(candidate, "__dict__"):
            candidate = vars(candidate)
        if not isinstance(candidate, Mapping):
            continue
        input_tokens = candidate.get("input_tokens", candidate.get("prompt_tokens"))
        output_tokens = candidate.get("output_tokens", candidate.get("completion_tokens"))
        total_tokens = candidate.get("total_tokens")
        usage: Dict[str, int] = {}
        try:
            if input_tokens is not None:
                usage["input_tokens"] = int(input_tokens)
            if output_tokens is not None:
                usage["output_tokens"] = int(output_tokens)
            if total_tokens is not None:
                usage["total_tokens"] = int(total_tokens)
        except (TypeError, ValueError):
            continue
        if usage:
            return usage
    return None


def _update_generation(handle: ObservationHandle, result: Any, client: Any) -> None:
    observation = handle.observation
    if observation is None:
        return
    kwargs: Dict[str, Any] = {"output": sanitise(result, key="llmOutput")}
    usage = _extract_usage(result, client)
    if usage:
        kwargs["usage_details"] = usage
    try:
        observation.update(**kwargs)
    except Exception:
        logger.debug("Could not update Langfuse generation", exc_info=True)


def instrument_llm_client(client: Any) -> Any:
    """Wrap a custom LLMClient's public completion methods as generations.

    Provider-native Langfuse integrations remain preferable. This wrapper is for
    custom clients that return text and otherwise hide the provider SDK.
    """
    if client is None or getattr(client, "_langfuse_instrumented", False):
        return client

    preferred_methods = [name for name in ("complete", "acomplete") if callable(getattr(client, name, None))]
    method_names = preferred_methods or [
        name for name in ("generate", "agenerate") if callable(getattr(client, name, None))
    ]
    for method_name in method_names:
        original = getattr(client, method_name, None)
        if original is None or not callable(original):
            continue
        if getattr(original, "_langfuse_wrapped", False):
            continue

        if inspect.iscoroutinefunction(original):
            @functools.wraps(original)
            async def async_wrapper(*args: Any, __original: Any = original, __name: str = method_name, **kwargs: Any) -> Any:
                request_input = args[0] if args else kwargs.get("messages", kwargs.get("prompt"))
                with trace_span(
                    f"llm-{__name}",
                    as_type="generation",
                    input_data=request_input,
                    model=_infer_model(client),
                    model_parameters=_model_parameters(kwargs),
                    metadata={"clientClass": client.__class__.__name__},
                ) as generation:
                    result = await __original(*args, **kwargs)
                    _update_generation(generation, result, client)
                    return result
            async_wrapper._langfuse_wrapped = True  # type: ignore[attr-defined]
            setattr(client, method_name, async_wrapper)
        else:
            @functools.wraps(original)
            def sync_wrapper(*args: Any, __original: Any = original, __name: str = method_name, **kwargs: Any) -> Any:
                request_input = args[0] if args else kwargs.get("messages", kwargs.get("prompt"))
                with trace_span(
                    f"llm-{__name}",
                    as_type="generation",
                    input_data=request_input,
                    model=_infer_model(client),
                    model_parameters=_model_parameters(kwargs),
                    metadata={"clientClass": client.__class__.__name__},
                ) as generation:
                    result = __original(*args, **kwargs)
                    _update_generation(generation, result, client)
                    return result
            sync_wrapper._langfuse_wrapped = True  # type: ignore[attr-defined]
            setattr(client, method_name, sync_wrapper)

    setattr(client, "_langfuse_instrumented", True)
    return client


def record_score(
    *,
    trace_id: str,
    name: str = "user-thumbs",
    value: float,
    comment: Optional[str] = None,
) -> bool:
    """Attach explicit user feedback to a trace using a BOOLEAN score."""
    if not re.fullmatch(r"[0-9a-f]{32}", (trace_id or "").strip().lower()):
        return False
    client = get_langfuse_client()
    if client is None:
        return False
    score_name = re.sub(r"[^a-z0-9-]", "-", (name or "user-thumbs").strip().lower())[:100]
    if not score_name:
        score_name = "user-thumbs"
    safe_comment = None
    if comment and _env_true("LANGFUSE_CAPTURE_FEEDBACK_COMMENTS", default=False):
        safe_comment = _EMAIL_RE.sub("[redacted-email]", comment)[:500]
    try:
        client.create_score(
            trace_id=trace_id.lower(),
            name=score_name,
            value=1.0 if float(value) >= 0.5 else 0.0,
            data_type="BOOLEAN",
            comment=safe_comment,
        )
        return True
    except Exception:
        logger.exception("Could not record Langfuse score")
        return False


def shutdown_langfuse() -> None:
    """Flush pending spans during graceful application shutdown."""
    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        logger.exception("Langfuse flush failed")
    shutdown = getattr(client, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown()
        except Exception:
            logger.debug("Langfuse shutdown failed", exc_info=True)
