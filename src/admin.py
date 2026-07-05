#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
管理员业务逻辑模块

提供管理后台所需的业务逻辑：
- 用户管理（CRUD、搜索、批量操作）
- 订阅管理（查看、更新状态）
- AI 监控（LLM 调用统计、缓存命中率、延迟分布）
- AI 评估（质量评分汇总、反馈分析）
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ---- 缓存统计 ----

def get_cache_stats() -> Dict[str, Any]:
    """获取所有缓存实例的统计信息"""
    from src.cache import (
        homework_cache, review_cache, explain_cache,
        practice_cache, subject_extraction_cache, profile_parse_cache,
    )
    return {
        "homework": homework_cache.stats,
        "review": review_cache.stats,
        "explain": explain_cache.stats,
        "practice": practice_cache.stats,
        "subject_extraction": subject_extraction_cache.stats,
        "profile_parse": profile_parse_cache.stats,
        "total": {
            "size": sum(len(c) for c in [
                homework_cache, review_cache, explain_cache,
                practice_cache, subject_extraction_cache, profile_parse_cache,
            ]),
        },
    }


def clear_all_caches() -> Dict[str, int]:
    """清空所有缓存，返回各缓存清除前的条目数"""
    from src.cache import (
        homework_cache, review_cache, explain_cache,
        practice_cache, subject_extraction_cache, profile_parse_cache,
    )
    caches = {
        "homework": homework_cache,
        "review": review_cache,
        "explain": explain_cache,
        "practice": practice_cache,
        "subject_extraction": subject_extraction_cache,
        "profile_parse": profile_parse_cache,
    }
    result = {}
    for name, cache in caches.items():
        result[name] = len(cache)
        cache.clear()
    return result


# ---- AI 监控 ----

def get_ai_metrics() -> Dict[str, Any]:
    """获取 AI 系统运行指标"""
    cache_stats = get_cache_stats()

    # 从 progress_db 获取作业统计
    from src.progress_db import get_all_sessions_summary
    session_summary = get_all_sessions_summary()

    return {
        "sessions": session_summary,
        "cache": cache_stats,
        "system": {
            "langfuse_enabled": _check_langfuse(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def _check_langfuse() -> bool:
    """检查 Langfuse 是否可用"""
    try:
        from src.observability import _get_client
        return _get_client() is not None
    except Exception:
        return False


# ---- AI 评估 ----

def get_evaluation_summary() -> Dict[str, Any]:
    """获取 AI 质量评估汇总"""
    from src.progress_db import get_all_sessions_summary

    summary = get_all_sessions_summary()

    # 计算各分数段分布
    conn = None
    try:
        from src.progress_db import _get_db
        conn = _get_db()
        score_distribution = conn.execute(
            """SELECT
                CASE
                    WHEN score >= 9 THEN '9-10 (Excellent)'
                    WHEN score >= 7 THEN '7-8 (Good)'
                    WHEN score >= 5 THEN '5-6 (Average)'
                    WHEN score >= 3 THEN '3-4 (Needs Improvement)'
                    ELSE '0-2 (Poor)'
                END as range_name,
                COUNT(*) as count
               FROM homework_sessions
               WHERE score IS NOT NULL
               GROUP BY range_name
               ORDER BY range_name"""
        ).fetchall()
    except Exception:
        score_distribution = []

    return {
        "total_reviews": summary["total_sessions"],
        "average_score": summary["average_score"],
        "score_distribution": [dict(r) for r in score_distribution],
        "by_subject": summary["by_subject"],
        "daily_trend": summary["daily_activity"],
    }


# ---- 订阅管理 ----

def get_subscription_overview() -> Dict[str, Any]:
    """获取订阅概览（从 Stripe 获取数据）"""
    try:
        import stripe
        # 获取活跃订阅数量
        subscriptions = stripe.Subscription.list(limit=100, status="active")
        active_count = len(subscriptions.data)

        # 获取总收入估算
        total_revenue = sum(
            sub.items.data[0].price.unit_amount * 0.01
            for sub in subscriptions.data
            if sub.items.data
        )

        return {
            "active_subscriptions": active_count,
            "estimated_revenue_gbp": round(total_revenue, 2),
            "subscriptions": [
                {
                    "id": sub.id,
                    "customer": sub.customer,
                    "status": sub.status,
                    "created": datetime.fromtimestamp(sub.created).isoformat(),
                }
                for sub in subscriptions.data[:20]
            ],
        }
    except ImportError:
        return {"error": "Stripe not installed", "active_subscriptions": 0}
    except Exception as e:
        logger.warning("[Admin] Stripe 查询失败: %s", e)
        return {"error": str(e), "active_subscriptions": 0}


# ---- 管理员认证（简单 token 验证） ----

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


def verify_admin_token(token: str) -> bool:
    """验证管理员 token

    如果 ADMIN_TOKEN 环境变量未设置，则允许所有请求（开发模式）。
    生产环境必须设置 ADMIN_TOKEN。
    """
    if not ADMIN_TOKEN:
        return True  # 开发模式：未设置 token 时允许所有请求
    return token == ADMIN_TOKEN
