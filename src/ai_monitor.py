#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AI 监控模块

记录每次 LLM 请求的详细信息，包括：
- 请求参数（prompt、RAG 上下文）
- 响应内容
- 延迟、token 用量
- 提供商、模型
- 作业元数据、Langfuse trace ID

提供查询和统计接口供管理后台使用。
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.progress_db import _get_db

logger = logging.getLogger(__name__)


def log_llm_request(
    provider: str,
    model: str,
    latency_ms: float,
    status: str = "success",
    prompt_tokens: int = None,
    completion_tokens: int = None,
    total_tokens: int = None,
    error_message: str = None,
    prompt_text: str = None,
    response_text: str = None,
    rag_context: str = None,
    student_id: str = None,
    subject: str = None,
    homework_doc_id: str = None,
    langfuse_trace_id: str = None,
    metadata: Dict[str, Any] = None,
    operation: str = None,
) -> str:
    """记录一次 LLM 请求

    Args:
        provider: LLM 提供商 (ollama, openai, etc.)
        model: 使用的模型名称
        latency_ms: 请求延迟（毫秒）
        status: 请求状态 (success, error)
        prompt_tokens: 输入 token 数
        completion_tokens: 输出 token 数
        total_tokens: 总 token 数
        error_message: 错误信息（如果有）
        prompt_text: 请求的 prompt 文本
        response_text: 模型响应文本
        rag_context: RAG 检索的上下文
        student_id: 关联的学生 ID
        subject: 关联的科目
        homework_doc_id: 关联的作业文档 ID
        langfuse_trace_id: Langfuse trace ID
        metadata: 额外的元数据
        operation: 操作类型 (homework, review, explain, practice, etc.)

    Returns:
        请求 ID
    """
    request_id = str(uuid.uuid4())
    conn = _get_db()

    # 截断过长的文本（避免数据库过大）
    max_text_len = 5000
    if prompt_text and len(prompt_text) > max_text_len:
        prompt_text = prompt_text[:max_text_len] + "... [truncated]"
    if response_text and len(response_text) > max_text_len:
        response_text = response_text[:max_text_len] + "... [truncated]"
    if rag_context and len(rag_context) > max_text_len:
        rag_context = rag_context[:max_text_len] + "... [truncated]"

    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    try:
        conn.execute(
            """INSERT INTO ai_requests
               (request_id, provider, model, operation, prompt_tokens, completion_tokens,
                total_tokens, latency_ms, status, error_message, prompt_text, response_text,
                rag_context, student_id, subject, homework_doc_id, langfuse_trace_id, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id, provider, model, operation,
                prompt_tokens, completion_tokens, total_tokens,
                latency_ms, status, error_message,
                prompt_text, response_text, rag_context,
                student_id, subject, homework_doc_id, langfuse_trace_id,
                metadata_json,
            ),
        )
        conn.commit()
        logger.debug("[AI Monitor] 记录请求: %s %s %.0fms", provider, model, latency_ms)
    except Exception as e:
        logger.error("[AI Monitor] 记录请求失败: %s", e)

    return request_id


def get_recent_requests(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """获取最近的 LLM 请求记录

    Args:
        limit: 返回数量
        offset: 偏移量

    Returns:
        请求记录列表
    """
    conn = _get_db()
    rows = conn.execute(
        """SELECT request_id, timestamp, provider, model, operation,
                  prompt_tokens, completion_tokens, total_tokens,
                  latency_ms, status, error_message,
                  student_id, subject, homework_doc_id, langfuse_trace_id
           FROM ai_requests
           ORDER BY timestamp DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_request_detail(request_id: str) -> Optional[Dict[str, Any]]:
    """获取单个请求的详细信息

    Args:
        request_id: 请求 ID

    Returns:
        请求详情（包含完整 prompt 和 response）
    """
    conn = _get_db()
    row = conn.execute(
        """SELECT * FROM ai_requests WHERE request_id = ?""",
        (request_id,),
    ).fetchone()
    return dict(row) if row else None


def get_ai_stats(hours: int = 24) -> Dict[str, Any]:
    """获取 AI 系统统计信息

    Args:
        hours: 统计时间范围（小时）

    Returns:
        统计信息字典
    """
    conn = _get_db()
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    # 总请求数
    total = conn.execute(
        "SELECT COUNT(*) FROM ai_requests WHERE timestamp > ?",
        (since,),
    ).fetchone()[0]

    # 成功/失败数
    success = conn.execute(
        "SELECT COUNT(*) FROM ai_requests WHERE timestamp > ? AND status = 'success'",
        (since,),
    ).fetchone()[0]
    errors = total - success

    # 平均延迟
    avg_latency = conn.execute(
        "SELECT AVG(latency_ms) FROM ai_requests WHERE timestamp > ? AND status = 'success'",
        (since,),
    ).fetchone()[0] or 0

    # Token 统计
    token_stats = conn.execute(
        """SELECT
            SUM(prompt_tokens) as total_prompt,
            SUM(completion_tokens) as total_completion,
            SUM(total_tokens) as total_tokens
           FROM ai_requests
           WHERE timestamp > ? AND status = 'success'""",
        (since,),
    ).fetchone()

    # 按提供商统计
    by_provider = conn.execute(
        """SELECT provider, COUNT(*) as count, AVG(latency_ms) as avg_latency
           FROM ai_requests
           WHERE timestamp > ?
           GROUP BY provider""",
        (since,),
    ).fetchall()

    # 按模型统计
    by_model = conn.execute(
        """SELECT model, COUNT(*) as count, AVG(latency_ms) as avg_latency,
                  SUM(total_tokens) as total_tokens
           FROM ai_requests
           WHERE timestamp > ?
           GROUP BY model""",
        (since,),
    ).fetchall()

    # 按操作类型统计
    by_operation = conn.execute(
        """SELECT operation, COUNT(*) as count
           FROM ai_requests
           WHERE timestamp > ? AND operation IS NOT NULL
           GROUP BY operation""",
        (since,),
    ).fetchall()

    # 每小时请求数（用于图表）
    hourly = conn.execute(
        """SELECT
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            COUNT(*) as count
           FROM ai_requests
           WHERE timestamp > ?
           GROUP BY hour
           ORDER BY hour""",
        (since,),
    ).fetchall()

    return {
        "total_requests": total,
        "success_count": success,
        "error_count": errors,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        "avg_latency_ms": round(avg_latency, 1),
        "total_prompt_tokens": token_stats["total_prompt"] or 0,
        "total_completion_tokens": token_stats["total_completion"] or 0,
        "total_tokens": token_stats["total_tokens"] or 0,
        "by_provider": [dict(r) for r in by_provider],
        "by_model": [dict(r) for r in by_model],
        "by_operation": [dict(r) for r in by_operation],
        "hourly_requests": [dict(r) for r in hourly],
        "period_hours": hours,
    }


def get_requests_by_filter(
    provider: str = None,
    model: str = None,
    status: str = None,
    student_id: str = None,
    subject: str = None,
    operation: str = None,
    start_time: str = None,
    end_time: str = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """按条件筛选请求记录

    Args:
        provider: 提供商筛选
        model: 模型筛选
        status: 状态筛选
        student_id: 学生 ID 筛选
        subject: 科目筛选
        operation: 操作类型筛选
        start_time: 开始时间
        end_time: 结束时间
        limit: 返回数量

    Returns:
        请求记录列表
    """
    conn = _get_db()
    conditions = []
    params = []

    if provider:
        conditions.append("provider = ?")
        params.append(provider)
    if model:
        conditions.append("model = ?")
        params.append(model)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if student_id:
        conditions.append("student_id = ?")
        params.append(student_id)
    if subject:
        conditions.append("subject = ?")
        params.append(subject)
    if operation:
        conditions.append("operation = ?")
        params.append(operation)
    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    rows = conn.execute(
        f"""SELECT request_id, timestamp, provider, model, operation,
                   prompt_tokens, completion_tokens, total_tokens,
                   latency_ms, status, error_message,
                   student_id, subject, homework_doc_id, langfuse_trace_id
            FROM ai_requests
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_model_comparison() -> List[Dict[str, Any]]:
    """获取模型对比数据

    Returns:
        各模型的性能对比数据
    """
    conn = _get_db()
    rows = conn.execute(
        """SELECT
            model,
            COUNT(*) as request_count,
            AVG(latency_ms) as avg_latency,
            MIN(latency_ms) as min_latency,
            MAX(latency_ms) as max_latency,
            SUM(total_tokens) as total_tokens,
            AVG(total_tokens) as avg_tokens,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
           FROM ai_requests
           GROUP BY model
           ORDER BY request_count DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_conversations(student_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """获取对话历史（按学生分组）

    Args:
        student_id: 可选的学生 ID 筛选
        limit: 返回数量

    Returns:
        对话记录列表
    """
    conn = _get_db()
    conditions = ["student_id IS NOT NULL"]
    params = []

    if student_id:
        conditions.append("student_id = ?")
        params.append(student_id)

    where_clause = " AND ".join(conditions)
    params.append(limit)

    rows = conn.execute(
        f"""SELECT request_id, timestamp, provider, model, operation,
                   prompt_text, response_text, student_id, subject
            FROM ai_requests
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
