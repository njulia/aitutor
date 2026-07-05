#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Langfuse 可观测性追踪模块

集成 Langfuse 进行 LLM 调用的全链路追踪、成本监控和质量评估。
- 所有 LLM 调用自动记录（input / output / tokens / latency / model）
- 支持端到端 Trace：用户请求 -> RAG 检索 -> LLM 调用 -> 响应
- 支持前端反馈评分（thumbs up/down）上报
- Langfuse 不可用时自动降级为 no-op，不影响业务

环境变量配置：
  LANGFUSE_PUBLIC_KEY  - Langfuse 项目 public key
  LANGFUSE_SECRET_KEY  - Langfuse 项目 secret key
  LANGFUSE_HOST        - Langfuse 自部署地址（默认 http://localhost:3000）
  LANGFUSE_ENABLED     - 设为 "false" 可禁用追踪（默认 true）
"""

import contextvars
import json
import logging
import os
import time
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# 当前请求的 trace 上下文（线程安全）
_current_trace: contextvars.ContextVar = contextvars.ContextVar(
    "langfuse_trace", default=None
)

# 懒加载的 Langfuse 客户端
_langfuse_client = None
_langfuse_available = None  # None = 未检测, True = 可用, False = 不可用


def _is_enabled() -> bool:
    """检查 Langfuse 是否启用"""
    return os.environ.get("LANGFUSE_ENABLED", "true").lower() != "false"


def _get_client():
    """懒加载 Langfuse 客户端，不可用时返回 None"""
    global _langfuse_client, _langfuse_available

    if not _is_enabled():
        _langfuse_available = False
        return None

    if _langfuse_available is False:
        return None

    if _langfuse_client is not None:
        return _langfuse_client

    try:
        from langfuse import Langfuse

        secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")

        if not secret_key or not public_key:
            logger.info(
                "[Langfuse] 环境变量未设置 (LANGFUSE_SECRET_KEY / LANGFUSE_PUBLIC_KEY)，"
                "追踪功能已禁用。设置后自动启用。"
            )
            _langfuse_available = False
            return None

        _langfuse_client = Langfuse(
            secret_key=secret_key,
            public_key=public_key,
            host=host,
        )
        _langfuse_available = True
        logger.info("[Langfuse] 已连接: %s", host)
        return _langfuse_client

    except ImportError:
        logger.info(
            "[Langfuse] langfuse 包未安装 (pip install langfuse)，追踪功能已禁用"
        )
        _langfuse_available = False
        return None
    except Exception as e:
        logger.warning("[Langfuse] 初始化失败: %s，追踪功能已禁用", e)
        _langfuse_available = False
        return None


def create_trace(
    name: str,
    user_id: str = None,
    session_id: str = None,
    metadata: Dict[str, Any] = None,
    input_data: Any = None,
) -> Optional[Any]:
    """创建一个新的 trace，表示一次完整的用户交互

    典型的使用场景：一次 API 请求对应一个 trace，
    其中包含多个 span（RAG 检索、LLM 调用等）。

    Args:
        name: trace 名称（如 "homework_review", "homework_generation"）
        user_id: 用户/学生 ID
        session_id: 会话 ID
        metadata: 附加元数据（如 year_group, subject, student_age）
        input_data: trace 的输入数据

    Returns:
        Langfuse trace 对象，不可用时返回 None
    """
    client = _get_client()
    if client is None:
        return None

    trace = client.trace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata or {},
        input=input_data,
    )
    _current_trace.set(trace)
    return trace


def get_current_trace():
    """获取当前上下文中的 trace"""
    return _current_trace.get()


def create_span(
    name: str,
    input_data: Any = None,
    output_data: Any = None,
    metadata: Dict[str, Any] = None,
    level: str = "DEFAULT",
) -> Optional[Any]:
    """在当前 trace 中创建一个 span

    Args:
        name: span 名称（如 "rag_retrieval", "llm_call", "generate_answer"）
        input_data: 输入数据
        output_data: 输出数据
        metadata: 附加元数据
        level: span 级别（DEBUG / DEFAULT / WARNING / ERROR）

    Returns:
        Langfuse span 对象，不可用时返回 None
    """
    client = _get_client()
    if client is None:
        return None

    trace = get_current_trace()
    if trace is None:
        return None

    span = trace.span(
        name=name,
        input=input_data,
        output=output_data,
        metadata=metadata or {},
        level=level,
    )
    return span


def record_llm_call(
    name: str,
    messages: Any,
    response: str,
    model: str,
    usage: Dict[str, int] = None,
    latency_ms: float = 0,
    metadata: Dict[str, Any] = None,
    level: str = "DEFAULT",
) -> Optional[Any]:
    """记录一次 LLM 调用

    这是最常用的入口 --- 每个 LLM 调用都经过这里。
    同时创建 trace span 和 Langfuse generation。

    Args:
        name: 调用名称（如 "homework_review", "deep_explain", "generate"）
        messages: 发送给 LLM 的消息列表
        response: LLM 返回的文本
        model: 模型名称
        usage: token 用量 {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
        latency_ms: 调用延迟（毫秒）
        metadata: 附加元数据（student_id, subject, year_group, cache_hit 等）
        level: 日志级别

    Returns:
        Langfuse generation 对象，不可用时返回 None
    """
    client = _get_client()
    if client is None:
        return None

    trace = get_current_trace()
    if trace is None:
        # 没有 trace 时创建独立 generation
        trace = client.trace(name=name, metadata=metadata or {})

    gen = trace.generation(
        name=name,
        model=model,
        input=messages,
        output=response,
        usage=usage,
        metadata={**(metadata or {}), "latency_ms": latency_ms},
        level=level,
    )
    return gen


def record_score(
    trace_id: str,
    name: str,
    value: float,
    comment: str = None,
) -> bool:
    """记录质量评分（前端 thumbs up/down 反馈）

    Args:
        trace_id: 关联的 trace ID
        name: 评分名称（如 "user_feedback", "answer_quality"）
        value: 分数（如 1.0 = thumbs up, 0.0 = thumbs down）
        comment: 可选文字反馈

    Returns:
        True 如果成功，False 如果 Langfuse 不可用
    """
    client = _get_client()
    if client is None:
        return False
    try:
        client.score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
        )
        client.flush()
        logger.debug("[Langfuse] 评分已记录: trace=%s name=%s value=%s", trace_id, name, value)
        return True
    except Exception as e:
        logger.warning("[Langfuse] 评分记录失败: %s", e)
        return False


def flush():
    """确保所有追踪数据已发送到 Langfuse 服务器"""
    client = _get_client()
    if client:
        try:
            client.flush()
        except Exception:
            pass


def shutdown():
    """关闭 Langfuse 连接"""
    global _langfuse_client, _langfuse_available
    if _langfuse_client:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
        except Exception:
            pass
        _langfuse_client = None
    _langfuse_available = None
