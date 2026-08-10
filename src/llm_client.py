#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
轻量级 LLM 客户端

支持三种后端：
1. Ollama 本地模型（开发/测试，零 API 费用）
2. OpenAI 兼容 API（DeepSeek 等）
3. Google Vertex AI（Gemini，使用 Application Default Credentials）

Quick/detail calls can use different providers through
QUICK_REVIEW_PROVIDER and DETAIL_REVIEW_PROVIDER.
"""

import json
import logging
import os
import random
import threading
import time
from copy import copy
from typing import Dict, List, Optional, Any

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

# AI 监控模块（懒加载，避免循环依赖）
_ai_monitor = None


def _get_ai_monitor():
    global _ai_monitor
    if _ai_monitor is None:
        try:
            from src.ai_monitor import log_llm_request
            _ai_monitor = log_llm_request
        except Exception:
            _ai_monitor = False
    return _ai_monitor if _ai_monitor is not False else None

# Langfuse 追踪模块（懒导入，不可用时不影响业务）
_observability = None


def _get_obs():
    global _observability
    if _observability is None:
        try:
            from src.observability import record_llm_call as _record
            _observability = _record
        except Exception:
            _observability = False  # 标记为不可用
    return _observability if _observability is not False else None


# ---- 后端配置 ----

# OpenAI 兼容 API（生产环境）
DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY")
DEFAULT_API_BASE = (os.getenv("DEFAULT_ENDPOINT_OPENAI") or "https://api.openai.com/v1").rstrip("/") + "/"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or DEFAULT_API_KEY
DEEPSEEK_BASE_URL = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/") + "/"
QUICK_REVIEW_PROVIDER = (os.getenv("QUICK_REVIEW_PROVIDER") or "deepseek").strip().lower()
DETAIL_REVIEW_PROVIDER = (os.getenv("DETAIL_REVIEW_PROVIDER") or "vertex_ai").strip().lower()
QUICK_REVIEW_MODEL = os.getenv("QUICK_REVIEW_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash"
DETAIL_REVIEW_MODEL = os.getenv("DETAIL_REVIEW_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL") or QUICK_REVIEW_MODEL
VISION_MODEL = os.getenv("DEFAULT_VISION_MODEL", "qwen-plus")
GOOGLE_CLOUD_PROJECT = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
GOOGLE_CLOUD_LOCATION = (os.getenv("GOOGLE_CLOUD_LOCATION") or "global").strip()

# Ollama 本地模型（开发/测试）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")

# 重试配置. LLM_MAX_RETRIES counts retries after the first attempt.
MAX_RETRIES = max(0, min(int(os.getenv("LLM_MAX_RETRIES", "1")), 4))
RETRY_DELAY = max(0.1, float(os.getenv("LLM_RETRY_DELAY", "0.5")))
MAX_TIMEOUT = max(5, min(int(os.getenv("LLM_TIMEOUT_SECONDS", "60")), 300))
CONNECT_TIMEOUT = max(1, min(int(os.getenv("LLM_CONNECT_TIMEOUT_SECONDS", "5")), 30))
HTTP_POOL_CONNECTIONS = max(1, min(int(os.getenv("LLM_HTTP_POOL_CONNECTIONS", "8")), 64))
HTTP_POOL_MAXSIZE = max(1, min(int(os.getenv("LLM_HTTP_POOL_MAXSIZE", "24")), 128))
MAX_PROVIDER_CONCURRENCY = max(
    1, min(int(os.getenv("MAX_PROVIDER_CONCURRENCY", "24")), 128)
)
PROVIDER_QUEUE_TIMEOUT = max(
    1, min(int(os.getenv("PROVIDER_QUEUE_TIMEOUT_SECONDS", "15")), 60)
)

_HTTP_LOCAL = threading.local()
_VERTEX_CLIENTS: Dict[tuple[str, str], Any] = {}
_CLIENT_LOCK = threading.RLock()
_PROVIDER_SEMAPHORE = threading.BoundedSemaphore(MAX_PROVIDER_CONCURRENCY)


class ProviderCapacityError(TimeoutError):
    """Raised when this instance has no safe provider request slot."""


def _request_attempts() -> int:
    return max(1, int(MAX_RETRIES) + 1)


def _is_retryable_request_error(exc: requests.exceptions.RequestException) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        return True
    return status_code in {408, 409, 425, 429} or int(status_code) >= 500


def _retry_wait_seconds(exc: BaseException, attempt: int) -> float:
    response = getattr(exc, "response", None)
    retry_after = getattr(response, "headers", {}).get("Retry-After") if response is not None else None
    try:
        if retry_after is not None:
            return max(0.1, min(float(retry_after), 10.0))
    except (TypeError, ValueError):
        pass
    base = min(RETRY_DELAY * (2 ** max(0, attempt - 1)), 8.0)
    return base + random.uniform(0.0, min(0.25 * base, 0.5))


def _normalise_provider(provider: str) -> str:
    value = str(provider or "").strip().lower().replace("-", "_")
    aliases = {
        "vertex": "vertex_ai",
        "vertexai": "vertex_ai",
        "google_vertex_ai": "vertex_ai",
        "openai_compatible": "api",
    }
    value = aliases.get(value, value)
    if value not in {"ollama", "api", "deepseek", "vertex_ai"}:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return value


def get_llm_provider() -> str:
    """Return the base provider; production defaults to the quick route."""
    return _normalise_provider(os.getenv("LLM_PROVIDER") or QUICK_REVIEW_PROVIDER)


class LLMClient:
    """Lightweight client supporting Ollama, DeepSeek and Vertex AI."""

    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        api_base: str = None,
        provider: str = None,
        temperature: float = 0.8,
        max_tokens: int = 1024,
    ):
        self.provider = _normalise_provider(provider or get_llm_provider())
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Langfuse 追踪上下文（由 web_app 等调用方设置）
        self.observe_metadata: Dict[str, Any] = {}

        self.model = model or (OLLAMA_MODEL if self.provider == "ollama" else DEFAULT_MODEL)
        self._configure_provider(self.provider, api_key=api_key, api_base=api_base)

    def _configure_provider(
        self,
        provider: str,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> None:
        self.provider = _normalise_provider(provider)
        if self.provider == "ollama":
            self.api_base = OLLAMA_BASE_URL.rstrip("/")
            self.api_key = None
        elif self.provider == "vertex_ai":
            self.api_base = None
            self.api_key = None
            self.vertex_project = (os.getenv("GOOGLE_CLOUD_PROJECT") or GOOGLE_CLOUD_PROJECT).strip()
            self.vertex_location = (os.getenv("GOOGLE_CLOUD_LOCATION") or GOOGLE_CLOUD_LOCATION).strip()
            if not self.vertex_project:
                raise ValueError("GOOGLE_CLOUD_PROJECT is required for the Vertex AI provider")
        else:
            default_key = DEEPSEEK_API_KEY if self.provider == "deepseek" else DEFAULT_API_KEY
            default_base = DEEPSEEK_BASE_URL if self.provider == "deepseek" else DEFAULT_API_BASE
            self.api_key = api_key or default_key
            self.api_base = (api_base or default_base).rstrip("/") + "/"
            if not self.api_key:
                key_name = "DEEPSEEK_API_KEY" if self.provider == "deepseek" else "DEFAULT_API_KEY"
                raise ValueError(f"{key_name} is required for the {self.provider} provider")
        logger.info("[LLM] provider=%s model=%s", self.provider, self.model)

    def is_ollama(self) -> bool:
        """是否使用 Ollama 后端"""
        return self.provider == "ollama"

    @staticmethod
    def _http_session() -> requests.Session:
        """Return a per-worker-thread keep-alive session.

        The web runtime reuses a bounded thread pool, so each thread also reuses
        its provider connections without sharing mutable Session state between
        threads.
        """
        session = getattr(_HTTP_LOCAL, "session", None)
        if session is None:
            session = requests.Session()
            adapter = HTTPAdapter(
                pool_connections=HTTP_POOL_CONNECTIONS,
                pool_maxsize=HTTP_POOL_MAXSIZE,
                max_retries=0,
                pool_block=True,
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            _HTTP_LOCAL.session = session
        return session

    def _post(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", (CONNECT_TIMEOUT, MAX_TIMEOUT))
        if not _PROVIDER_SEMAPHORE.acquire(timeout=PROVIDER_QUEUE_TIMEOUT):
            raise ProviderCapacityError(
                "The AI provider queue is full on this service instance"
            )
        try:
            return self._http_session().post(url, **kwargs)
        finally:
            _PROVIDER_SEMAPHORE.release()

    def provider_for_model(self, model: str) -> str:
        """Resolve a model tier to its configured provider."""
        if self.provider == "ollama":
            return "ollama"
        selected_model = str(model or "").strip()
        if selected_model == DETAIL_REVIEW_MODEL:
            return _normalise_provider(os.getenv("DETAIL_REVIEW_PROVIDER") or DETAIL_REVIEW_PROVIDER)
        if selected_model == QUICK_REVIEW_MODEL:
            return _normalise_provider(os.getenv("QUICK_REVIEW_PROVIDER") or QUICK_REVIEW_PROVIDER)
        return self.provider

    def with_model(self, model: str) -> "LLMClient":
        """Return a request-local client view pinned to one model."""
        selected_model = str(model or "").strip()
        if not selected_model:
            raise ValueError("model must not be empty")
        route_provider = self.provider_for_model(selected_model)
        if route_provider == "ollama":
            env_name = (
                "OLLAMA_DETAIL_REVIEW_MODEL"
                if selected_model == DETAIL_REVIEW_MODEL
                else "OLLAMA_QUICK_REVIEW_MODEL"
            )
            selected_model = os.getenv(env_name) or self.model
        client = copy(self)
        client.model = selected_model
        client.observe_metadata = dict(self.observe_metadata)
        client._configure_provider(route_provider)
        return client

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        model: str = None,
    ) -> str:
        """发送聊天补全请求，返回文本响应

        Args:
            messages: 消息列表
            temperature: 温度参数（可选）
            max_tokens: 最大 token 数（可选）
            model: 可选的单次调用模型覆盖，用于 Flash/Plus 路由

        Returns:
            模型回复的文本内容
        """
        selected_model = (model or self.model).strip()
        route_provider = self.provider_for_model(selected_model)
        if route_provider != self.provider:
            return self.with_model(selected_model).complete(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if self.is_ollama():
            return self._ollama_complete(messages, temperature, max_tokens, model=selected_model)
        if self.provider == "vertex_ai":
            return self._vertex_complete(messages, temperature, max_tokens, model=selected_model)
        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        return self._request(payload)

    def complete_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Any:
        """发送聊天补全请求，将响应解析为 JSON

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            解析后的 JSON 对象
        """
        text = self.complete(messages, temperature, max_tokens)
        text = text.strip()
        # 去除可能的 markdown 代码块包裹
        if text.startswith("```"):
            first_newline = text.index("\n") if "\n" in text else 3
            text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)

    def vision_complete(
        self,
        prompt: str,
        image_base64: str,
        temperature: float = 0,
        max_tokens: int = 1024,
    ) -> str:
        """发送带图片的视觉聊天请求（用于 OCR 等）

        Args:
            prompt: 文本提示
            image_base64: 图片的 base64 编码字符串
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            模型回复的文本内容
        """
        if self.is_ollama():
            return self._ollama_vision(prompt, image_base64, temperature, max_tokens)

        payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._request(payload)

    def complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Dict:
        """发送带工具定义的聊天补全请求

        Args:
            messages: 消息列表
            tools: OpenAI 格式的工具定义列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            完整的响应消息 dict（包含 content 和可能的 tool_calls）
        """
        if self.is_ollama():
            # Ollama 也支持 OpenAI 兼容的 tools 格式
            return self._ollama_complete_with_tools(messages, tools, temperature, max_tokens)

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        return self._request_raw(payload)

    # ================================================================
    # Ollama 本地模型调用
    # ================================================================

    def _ollama_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        model: str = None,
    ) -> str:
        """通过 Ollama 的 OpenAI 兼容接口发送聊天请求"""
        url = f"{self.api_base}/v1/chat/completions"
        selected_model = (model or self.model).strip()
        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": False,
            "thinking": {"type": "disabled"}
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        t_start = time.time()

        attempts = _request_attempts()
        for attempt in range(1, attempts + 1):
            try:
                resp = self._post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                latency_ms = (time.time() - t_start) * 1000
                logger.debug(
                    "[LLM:Ollama] model=%s latency=%.0fms",
                    selected_model, latency_ms,
                )

                # AI 监控记录
                monitor = _get_ai_monitor()
                if monitor:
                    try:
                        monitor(
                            provider="ollama",
                            model=selected_model,
                            latency_ms=latency_ms,
                            status="success",
                            prompt_text=str(messages)[:2000] if messages else None,
                            response_text=content[:2000] if content else None,
                            operation=self.observe_metadata.get("operation"),
                            student_id=self.observe_metadata.get("student_id"),
                            subject=self.observe_metadata.get("subject"),
                        )
                    except Exception:
                        pass

                return content

            except requests.exceptions.RequestException as e:
                if attempt < attempts and _is_retryable_request_error(e):
                    wait_seconds = _retry_wait_seconds(e, attempt)
                    logger.warning(
                        "[LLM:Ollama] request failed (attempt %d); retrying in %.1fs",
                        attempt, wait_seconds,
                    )
                    time.sleep(wait_seconds)
                else:
                    logger.error("[LLM:Ollama] 请求最终失败: %s", e)
                    raise

    def _ollama_vision(
        self,
        prompt: str,
        image_base64: str,
        temperature: float = 0,
        max_tokens: int = 1024,
    ) -> str:
        """通过 Ollama 发送视觉请求"""
        url = f"{self.api_base}/api/chat"
        payload = {
            "model": OLLAMA_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                }
            ],
            "stream": False,
            "thinking": {"type": "disabled"}
        }

        try:
            resp = self._post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except Exception as e:
            logger.error("[LLM:Ollama] 视觉请求失败: %s", e)
            raise

    def _ollama_complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Dict:
        """通过 Ollama 发送带工具调用的请求"""
        url = f"{self.api_base}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": False,
        }

        try:
            resp = self._post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]
        except Exception as e:
            logger.error("[LLM:Ollama] 工具调用请求失败: %s", e)
            # 降级：不带工具调用，返回纯文本
            return {"content": self._ollama_complete(messages, temperature, max_tokens)}

    # ================================================================
    # Google Vertex AI / Gemini
    # ================================================================

    def _get_vertex_client(self):
        key = (self.vertex_project, self.vertex_location)
        client = _VERTEX_CLIENTS.get(key)
        if client is not None:
            return client
        with _CLIENT_LOCK:
            client = _VERTEX_CLIENTS.get(key)
            if client is not None:
                return client
            try:
                from google import genai
                from google.genai.types import HttpOptions
            except ImportError as exc:
                raise RuntimeError(
                    "google-genai is required for DETAIL_REVIEW_PROVIDER=vertex_ai"
                ) from exc
            client = genai.Client(
                vertexai=True,
                project=self.vertex_project,
                location=self.vertex_location,
                http_options=HttpOptions(api_version="v1"),
            )
            _VERTEX_CLIENTS[key] = client
            return client

    @staticmethod
    def _vertex_contents(messages: List[Dict[str, str]]) -> tuple[list, Optional[str]]:
        contents = []
        system_parts = []
        for message in messages or []:
            role = str(message.get("role") or "user").strip().lower()
            text = message.get("content")
            if isinstance(text, list):
                text = "\n".join(str(part.get("text") or "") for part in text if isinstance(part, dict))
            text = str(text or "")
            if role == "system":
                system_parts.append(text)
                continue
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": text}],
            })
        return contents, "\n\n".join(part for part in system_parts if part) or None

    def _vertex_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        model: str = None,
    ) -> str:
        try:
            from google.genai.types import GenerateContentConfig
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is required for DETAIL_REVIEW_PROVIDER=vertex_ai"
            ) from exc

        selected_model = str(model or self.model).strip()
        contents, system_instruction = self._vertex_contents(messages)
        config = GenerateContentConfig(
            temperature=temperature if temperature is not None else self.temperature,
            max_output_tokens=max_tokens or self.max_tokens,
            system_instruction=system_instruction,
        )
        started = time.time()
        attempts = _request_attempts()
        for attempt in range(1, attempts + 1):
            try:
                if not _PROVIDER_SEMAPHORE.acquire(timeout=PROVIDER_QUEUE_TIMEOUT):
                    raise ProviderCapacityError(
                        "The AI provider queue is full on this service instance"
                    )
                try:
                    response = self._get_vertex_client().models.generate_content(
                        model=selected_model,
                        contents=contents,
                        config=config,
                    )
                finally:
                    _PROVIDER_SEMAPHORE.release()
                content = str(getattr(response, "text", "") or "")
                # Gemini 3.6+ 的 text 属性可能为空，从 candidates 中提取文本
                if not content:
                    candidates = getattr(response, "candidates", None) or []
                    if candidates:
                        parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
                        content = "".join(str(getattr(p, "text", "") or "") for p in parts)
                usage_metadata = getattr(response, "usage_metadata", None)
                usage = {
                    "prompt_tokens": getattr(usage_metadata, "prompt_token_count", None),
                    "completion_tokens": getattr(usage_metadata, "candidates_token_count", None),
                    "total_tokens": getattr(usage_metadata, "total_token_count", None),
                }
                self._record_success(
                    messages=messages,
                    response=content,
                    model=selected_model,
                    usage={key: value for key, value in usage.items() if value is not None},
                    latency_ms=(time.time() - started) * 1000,
                )
                return content
            except Exception as exc:
                if attempt < attempts:
                    wait_seconds = _retry_wait_seconds(exc, attempt)
                    logger.warning(
                        "[LLM:VertexAI] request failed (attempt %d): %s; retrying in %.1fs",
                        attempt,
                        exc,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                else:
                    logger.error("[LLM:VertexAI] request failed: %s", exc)
                    raise

    # ================================================================
    # OpenAI 兼容 API 调用
    # ================================================================

    def _record_success(
        self,
        *,
        messages: List[Dict[str, str]],
        response: str,
        model: str,
        usage: Optional[Dict[str, Any]],
        latency_ms: float,
    ) -> None:
        usage = usage or {}
        obs = _get_obs()
        if obs:
            try:
                obs(
                    name=self.observe_metadata.get("name", "llm_call"),
                    messages=messages,
                    response=response,
                    model=model,
                    usage=usage or None,
                    latency_ms=latency_ms,
                    metadata={**self.observe_metadata, "provider": self.provider},
                )
            except Exception:
                pass

        monitor = _get_ai_monitor()
        if monitor:
            try:
                monitor(
                    provider=self.provider,
                    model=model,
                    latency_ms=latency_ms,
                    status="success",
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    prompt_text=str(messages)[:2000],
                    response_text=(response or "")[:2000],
                    operation=self.observe_metadata.get("operation"),
                    student_id=self.observe_metadata.get("student_id"),
                    subject=self.observe_metadata.get("subject"),
                )
            except Exception:
                pass

    def _request(self, payload: Dict) -> str:
        """发送请求并返回文本内容（带重试）"""
        response = self._request_raw(payload)
        return response.get("content", "")

    def _request_raw(self, payload: Dict) -> Dict:
        """发送请求并返回完整的消息 dict（带重试）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.api_base}chat/completions"
        selected_model = str(payload.get("model") or self.model)

        t_start = time.time()

        attempts = _request_attempts()
        for attempt in range(1, attempts + 1):
            try:
                resp = self._post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                message = data["choices"][0]["message"]
                usage = data.get("usage", {})

                # 记录 token 用量
                if usage:
                    logger.debug(
                        "[LLM] model=%s tokens: prompt=%s completion=%s total=%s",
                        selected_model,
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                        usage.get("total_tokens", 0),
                    )

                latency_ms = (time.time() - t_start) * 1000
                self._record_success(
                    messages=payload.get("messages", []),
                    response=message.get("content", ""),
                    model=selected_model,
                    usage=usage,
                    latency_ms=latency_ms,
                )

                return message

            except requests.exceptions.RequestException as e:
                if attempt < attempts and _is_retryable_request_error(e):
                    wait_seconds = _retry_wait_seconds(e, attempt)
                    logger.warning(
                        "[LLM] request failed (attempt %d); retrying in %.1fs",
                        attempt, wait_seconds,
                    )
                    time.sleep(wait_seconds)
                else:
                    logger.error("[LLM] 请求最终失败: %s", e)
                    raise


# ---- 模块级便捷函数 ----

def format_prompt(template: str, **kwargs) -> str:
    """格式化 prompt 模板并进行轻量压缩以节省 token

    Args:
        template: 包含 {variable} 占位符的模板字符串
        **kwargs: 模板变量

    Returns:
        格式化并优化后的字符串
    """
    try:
        from src.prompt_utils import compact_format
        return compact_format(template, **kwargs)
    except Exception:
        return template.format(**kwargs)


def build_messages(user_content: str, system_content: str = None) -> List[Dict[str, str]]:
    """构建消息列表

    Args:
        user_content: 用户消息内容
        system_content: 系统消息内容（可选）

    Returns:
        消息列表
    """
    messages = []
    if system_content:
        messages.append({"role": "system", "content": system_content})
    messages.append({"role": "user", "content": user_content})
    return messages
