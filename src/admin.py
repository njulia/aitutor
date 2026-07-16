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


# ---- 开发模式判断 ----

def is_dev_mode() -> bool:
    """判断是否处于开发模式（绕过 Stripe）"""
    return os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")


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
        from src.observability import get_langfuse_client
        return get_langfuse_client() is not None
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
    """Return locally materialised entitlements.

    Stripe webhooks are the source of change, while PostgreSQL is the source
    used by the application and dashboard. This avoids slow live list calls and
    keeps entitlement decisions deterministic.
    """
    if is_dev_mode():
        from src.progress_db import get_local_subscription_stats
        legacy = get_local_subscription_stats()
    else:
        legacy = None
    from src.webapp.account_store import get_subscription_stats
    result = get_subscription_stats()
    if legacy:
        result["active_subscriptions"] += legacy.get("active_subscriptions", 0)
        # Merge legacy subscriptions into the main list if desired, or keep separate
        # The UI seems to only use data.subscriptions
        if "subscriptions" in result:
            result["subscriptions"] = legacy.get("subscriptions", []) + result["subscriptions"]
        
        result["legacy_dev_subscriptions"] = legacy
    return result


def create_admin_subscription(email: str, name: str, duration: str, plan: str = "homework_monthly") -> Dict[str, Any]:
    """Create a local test entitlement only in development.

    Production subscriptions must start in authenticated Stripe Checkout and
    become active only after a signed webhook has been processed.
    """
    if not is_dev_mode():
        raise ValueError(
            "Manual subscriptions are disabled in production. Use Stripe Checkout and verified webhooks."
        )
    duration_days = {"5_days": 5, "30_days": 30}
    if duration not in duration_days:
        raise ValueError("Invalid duration, must be '5_days' or '30_days'")

    from src.progress_db import create_local_subscription
    from src.webapp.account_store import ensure_account, create_subscription

    # 1. Create legacy subscription (for dev-mode compatibility)
    product_map = {
        "homework_monthly": "Homework Premium",
        "elevenplus_monthly": "11+ Premium",
        "family_monthly": "Family Premium"
    }
    product_name = product_map.get(plan, "Homework Premium")
    if duration == "5_days":
        product_name += " (5-Day Trial)"

    legacy = create_local_subscription(
        customer_email=email, customer_name=name, product_name=product_name,
        duration_days=duration_days[duration],
    )

    # 2. Also create a materialised entitlement in the new account store
    account = ensure_account(email)
    new_sub = create_subscription(
        account_id=account["id"],
        plan=plan,
        status="active",
        duration_days=duration_days[duration]
    )

    return {
        "legacy": legacy,
        "subscription": new_sub
    }


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
