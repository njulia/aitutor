#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
轻量级 LLM 客户端

支持两种后端：
1. Ollama 本地模型（开发/测试，零 API 费用）
2. OpenAI 兼容 API（QWEN 等，生产环境使用）

通过环境变量 LLM_PROVIDER 切换：
  - "ollama"：使用 Ollama 本地模型
  - "api"（默认）：使用 OpenAI 兼容 API
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Any

import requests

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
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL") or "gpt-4.1-mini"
VISION_MODEL = os.getenv("DEFAULT_VISION_MODEL", "qwen-plus")

# Ollama 本地模型（开发/测试）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")

# 重试配置
MAX_RETRIES = max(0, min(int(os.getenv("LLM_MAX_RETRIES", "1")), 4))
RETRY_DELAY = max(0.1, float(os.getenv("LLM_RETRY_DELAY", "0.5")))
MAX_TIMEOUT = max(5, min(int(os.getenv("LLM_TIMEOUT_SECONDS", "90")), 300))


def get_llm_provider() -> str:
    """获取当前 LLM 后端类型

    Returns:
        "ollama" 或 "api"
    """
    return os.getenv("LLM_PROVIDER", "ollama").lower()


class LLMClient:
    """轻量级 LLM 客户端，支持 Ollama 和 OpenAI 兼容 API"""

    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        api_base: str = None,
        temperature: float = 0.8,
        max_tokens: int = 1024,
    ):
        self.provider = get_llm_provider()
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Langfuse 追踪上下文（由 web_app 等调用方设置）
        self.observe_metadata: Dict[str, Any] = {}

        if self.provider == "ollama":
            # Ollama 本地模型
            self.model = model or OLLAMA_MODEL
            self.api_base = OLLAMA_BASE_URL.rstrip("/")
            self.api_key = None
            logger.info(
                "[LLM] 使用 Ollama 本地模型: %s @ %s",
                self.model, self.api_base,
            )
        else:
            # OpenAI 兼容 API
            self.model = model or DEFAULT_MODEL
            self.api_key = api_key or DEFAULT_API_KEY
            # Ensure api_base ends with a slash
            self.api_base = (api_base or DEFAULT_API_BASE).rstrip("/") + "/"

            if not self.api_key:
                raise ValueError(
                    "DEFAULT_API_KEY is not configured. Set it for the API provider, "
                    "or use LLM_PROVIDER=ollama for a local model."
                )
            logger.info(
                "[LLM] 使用 API 后端: model=%s base=%s",
                self.model, self.api_base,
            )

    def is_ollama(self) -> bool:
        """是否使用 Ollama 后端"""
        return self.provider == "ollama"

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
        if self.is_ollama():
            return self._ollama_complete(messages, temperature, max_tokens, model=selected_model)
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
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        t_start = time.time()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(url, json=payload, timeout=MAX_TIMEOUT)
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
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "[LLM:Ollama] 请求失败 (第 %d 次): %s, %d 秒后重试...",
                        attempt, e, RETRY_DELAY,
                    )
                    time.sleep(RETRY_DELAY)
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
        }

        try:
            resp = requests.post(url, json=payload, timeout=MAX_TIMEOUT)
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
            resp = requests.post(url, json=payload, timeout=MAX_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]
        except Exception as e:
            logger.error("[LLM:Ollama] 工具调用请求失败: %s", e)
            # 降级：不带工具调用，返回纯文本
            return {"content": self._ollama_complete(messages, temperature, max_tokens)}

    # ================================================================
    # OpenAI 兼容 API 调用
    # ================================================================

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

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=MAX_TIMEOUT)
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

                # Langfuse 追踪（不可用时自动跳过）
                latency_ms = (time.time() - t_start) * 1000
                obs = _get_obs()
                if obs:
                    try:
                        obs(
                            name=self.observe_metadata.get("name", "llm_call"),
                            messages=payload.get("messages", []),
                            response=message.get("content", ""),
                            model=selected_model,
                            usage=usage or None,
                            latency_ms=latency_ms,
                            metadata=self.observe_metadata,
                        )
                    except Exception:
                        pass  # 追踪失败不影响业务

                # AI 监控记录
                monitor = _get_ai_monitor()
                if monitor:
                    try:
                        monitor(
                            provider=self.provider,
                            model=selected_model,
                            latency_ms=latency_ms,
                            status="success",
                            prompt_tokens=usage.get("prompt_tokens") if usage else None,
                            completion_tokens=usage.get("completion_tokens") if usage else None,
                            total_tokens=usage.get("total_tokens") if usage else None,
                            prompt_text=str(payload.get("messages", []))[:2000],
                            response_text=(message.get("content") or "")[:2000],
                            operation=self.observe_metadata.get("operation"),
                            student_id=self.observe_metadata.get("student_id"),
                            subject=self.observe_metadata.get("subject"),
                        )
                    except Exception:
                        pass

                return message

            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "[LLM] 请求失败 (第 %d 次): %s, %d 秒后重试...",
                        attempt, e, RETRY_DELAY,
                    )
                    time.sleep(RETRY_DELAY)
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
