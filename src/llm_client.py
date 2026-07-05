#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
轻量级 OpenAI 兼容 API 客户端

直接调用 OpenAI 兼容的 API，替代 LangChain 以减少延迟和依赖。
支持文本、JSON、视觉（图片 OCR）三种调用模式。
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Any

import requests

logger = logging.getLogger(__name__)

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


# 默认配置
DEFAULT_API_BASE = "https://api.agicto.cn/v1/"
DEFAULT_MODEL = "deepseek-v4-flash"
VISION_MODEL = "qwen3.5-plus"

# 重试配置
MAX_RETRIES = 2
RETRY_DELAY = 1  # 秒


class LLMClient:
    """轻量级 OpenAI 兼容 API 客户端，用于替代 LangChain"""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str = None,
        api_base: str = DEFAULT_API_BASE,
        temperature: float = 0.8,
        max_tokens: int = 2048,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("AGICTO_API_KEY")
        self.api_base = api_base.rstrip("/") + "/"
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Langfuse 追踪上下文（由 web_app 等调用方设置）
        self.observe_metadata: Dict[str, Any] = {}

        if not self.api_key:
            raise ValueError(
                "AGICTO_API_KEY 环境变量未设置，请先设置: export AGICTO_API_KEY='your-key'"
            )

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """发送聊天补全请求，返回文本响应

        Args:
            messages: 消息列表，格式 [{"role": "system"|"user"|"assistant", "content": "..."}]
            temperature: 温度参数（可选，覆盖默认值）
            max_tokens: 最大 token 数（可选，覆盖默认值）

        Returns:
            模型回复的文本内容
        """
        payload = {
            "model": self.model,
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
            解析后的 JSON 对象（dict / list）
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
        max_tokens: int = 2048,
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
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        return self._request_raw(payload)

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

        t_start = time.time()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                message = data["choices"][0]["message"]
                usage = data.get("usage", {})

                # 记录 token 用量
                if usage:
                    logger.debug(
                        "[LLM] model=%s tokens: prompt=%s completion=%s total=%s",
                        self.model,
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
                            model=self.model,
                            usage=usage or None,
                            latency_ms=latency_ms,
                            metadata=self.observe_metadata,
                        )
                    except Exception:
                        pass  # 追踪失败不影响业务

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
    """格式化 prompt 模板，替代 LangChain 的 ChatPromptTemplate.from_template

    Args:
        template: 包含 {variable} 占位符的模板字符串
        **kwargs: 模板变量

    Returns:
        格式化后的字符串
    """
    return template.format(**kwargs)


def build_messages(user_content: str, system_content: str = None) -> List[Dict[str, str]]:
    """构建消息列表，替代 LangChain 的 prompt | llm 管道

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
