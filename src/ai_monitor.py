"""PostgreSQL-ready, privacy-safe AI request metrics."""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, and_, func, select

from src.progress_db import _engine, ai_requests


def _serialise(row: Any) -> Dict[str, Any]:
    data = dict(row._mapping)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def _allow_raw(metadata: Optional[Dict[str, Any]]) -> bool:
    server_enabled = os.getenv("STORE_RAW_AI_CONTENT", "false").lower() in {"1", "true", "yes", "on"}
    parent_opt_in = bool((metadata or {}).get("raw_logging_opt_in"))
    return server_enabled and parent_opt_in


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
    request_id = str(uuid.uuid4())
    raw = _allow_raw(metadata)
    max_len = 5000
    safe_metadata = {
        key: value for key, value in (metadata or {}).items()
        if key not in {"raw_logging_opt_in", "child_name", "email", "school"}
        and isinstance(value, (str, int, float, bool, type(None)))
    }
    with _engine.begin() as conn:
        conn.execute(ai_requests.insert().values(
            id=f"air_{uuid.uuid4().hex}", request_id=request_id, timestamp=datetime.now(UTC),
            provider=provider[:80], model=model[:120], operation=(operation or "")[:80] or None,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=total_tokens, latency_ms=latency_ms, status=status[:30],
            error_message=(error_message or "")[:1000] or None,
            prompt_text=(prompt_text or "")[:max_len] if raw else None,
            response_text=(response_text or "")[:max_len] if raw else None,
            rag_context=(rag_context or "")[:max_len] if raw else None,
            student_id=student_id, subject=subject, homework_doc_id=homework_doc_id,
            langfuse_trace_id=langfuse_trace_id,
            metadata_json=json.dumps(safe_metadata, ensure_ascii=False) if safe_metadata else None,
        ))
    return request_id


def get_recent_requests(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    columns = [ai_requests.c.request_id, ai_requests.c.timestamp, ai_requests.c.provider,
               ai_requests.c.model, ai_requests.c.operation, ai_requests.c.prompt_tokens,
               ai_requests.c.completion_tokens, ai_requests.c.total_tokens,
               ai_requests.c.latency_ms, ai_requests.c.status, ai_requests.c.error_message,
               ai_requests.c.student_id, ai_requests.c.subject,
               ai_requests.c.homework_doc_id, ai_requests.c.langfuse_trace_id]
    with _engine.begin() as conn:
        rows = conn.execute(select(*columns).order_by(ai_requests.c.timestamp.desc()).limit(max(1,min(limit,500))).offset(max(0,offset))).all()
    return [_serialise(row) for row in rows]


def get_request_detail(request_id: str) -> Optional[Dict[str, Any]]:
    with _engine.begin() as conn:
        row = conn.execute(select(ai_requests).where(ai_requests.c.request_id == request_id)).first()
    return _serialise(row) if row else None


def get_ai_stats(hours: int = 24) -> Dict[str, Any]:
    since = datetime.now(UTC) - timedelta(hours=max(1,min(hours,24*90)))
    condition = ai_requests.c.timestamp >= since
    with _engine.begin() as conn:
        total = conn.execute(select(func.count()).select_from(ai_requests).where(condition)).scalar_one()
        success = conn.execute(select(func.count()).select_from(ai_requests).where(and_(condition, ai_requests.c.status == "success"))).scalar_one()
        avg_latency = conn.execute(select(func.avg(ai_requests.c.latency_ms)).where(and_(condition, ai_requests.c.status == "success"))).scalar() or 0
        token_row = conn.execute(select(func.sum(ai_requests.c.prompt_tokens), func.sum(ai_requests.c.completion_tokens), func.sum(ai_requests.c.total_tokens)).where(condition)).first()
        provider_rows = conn.execute(select(ai_requests.c.provider, func.count().label("count"), func.avg(ai_requests.c.latency_ms).label("avg_latency")).where(condition).group_by(ai_requests.c.provider)).all()
        model_rows = conn.execute(select(ai_requests.c.model, func.count().label("count"), func.avg(ai_requests.c.latency_ms).label("avg_latency"), func.sum(ai_requests.c.total_tokens).label("total_tokens")).where(condition).group_by(ai_requests.c.model)).all()
        operation_rows = conn.execute(select(ai_requests.c.operation, func.count().label("count")).where(and_(condition, ai_requests.c.operation.is_not(None))).group_by(ai_requests.c.operation)).all()
    return {
        "total_requests": int(total), "success_count": int(success), "error_count": int(total-success),
        "success_rate": round(success/total*100,1) if total else 0,
        "avg_latency_ms": round(float(avg_latency),1),
        "total_prompt_tokens": int(token_row[0] or 0), "total_completion_tokens": int(token_row[1] or 0),
        "total_tokens": int(token_row[2] or 0),
        "by_provider": [_serialise(r) for r in provider_rows],
        "by_model": [_serialise(r) for r in model_rows],
        "by_operation": [_serialise(r) for r in operation_rows],
        "hourly_requests": [], "period_hours": hours,
    }


def get_requests_by_filter(
    provider: str = None, model: str = None, status: str = None,
    student_id: str = None, subject: str = None, operation: str = None,
    start_time: str = None, end_time: str = None, limit: int = 100,
) -> List[Dict[str, Any]]:
    conditions = []
    for column, value in ((ai_requests.c.provider,provider),(ai_requests.c.model,model),(ai_requests.c.status,status),(ai_requests.c.student_id,student_id),(ai_requests.c.subject,subject),(ai_requests.c.operation,operation)):
        if value: conditions.append(column == value)
    if start_time:
        try: conditions.append(ai_requests.c.timestamp >= datetime.fromisoformat(start_time))
        except ValueError: pass
    if end_time:
        try: conditions.append(ai_requests.c.timestamp <= datetime.fromisoformat(end_time))
        except ValueError: pass
    query = select(ai_requests)
    if conditions: query = query.where(and_(*conditions))
    with _engine.begin() as conn:
        rows = conn.execute(query.order_by(ai_requests.c.timestamp.desc()).limit(max(1,min(limit,500)))).all()
    return [_serialise(r) for r in rows]


def get_model_comparison() -> List[Dict[str, Any]]:
    with _engine.begin() as conn:
        rows = conn.execute(select(ai_requests.c.provider, ai_requests.c.model,
            func.count().label("request_count"), func.avg(ai_requests.c.latency_ms).label("avg_latency_ms"),
            func.avg(ai_requests.c.total_tokens).label("avg_tokens"),
            func.sum(func.cast(ai_requests.c.status == "success", __import__('sqlalchemy').Integer)).label("success_count")
        ).group_by(ai_requests.c.provider, ai_requests.c.model)).all()
    return [_serialise(r) for r in rows]


def get_conversations(student_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    query = select(ai_requests.c.request_id, ai_requests.c.timestamp, ai_requests.c.operation,
                   ai_requests.c.prompt_text, ai_requests.c.response_text, ai_requests.c.subject,
                   ai_requests.c.student_id).where(
        (ai_requests.c.prompt_text.is_not(None)) | (ai_requests.c.response_text.is_not(None))
    )
    if student_id:
        query = query.where(ai_requests.c.student_id == student_id)
    with _engine.begin() as conn:
        rows = conn.execute(query.order_by(ai_requests.c.timestamp.desc()).limit(max(1,min(limit,200)))).all()
    return [_serialise(r) for r in rows]


def delete_student_records(student_id: str) -> int:
    """Erase AI telemetry associated with a learner pseudonym."""
    with _engine.begin() as conn:
        result = conn.execute(delete(ai_requests).where(ai_requests.c.student_id == student_id))
    return int(result.rowcount or 0)
