#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TTL 缓存模块

为 AI Tutor 提供线程安全的内存缓存，减少重复的 LLM 调用，
降低延迟和 token 消耗，适合百万级用户的高并发场景。
"""

import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """线程安全的 LRU + TTL 缓存

    - 超过 TTL 的条目自动失效
    - 超过 max_size 时淘汰最久未使用的条目
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, "_CacheEntry"] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，过期或不存在返回 None"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.time() > entry.expires_at:
                # 已过期，删除
                del self._cache[key]
                self._misses += 1
                return None
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 自定义 TTL（秒），不传则使用默认值
        """
        with self._lock:
            expires_at = time.time() + (ttl if ttl is not None else self._ttl)
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = _CacheEntry(value=value, expires_at=expires_at)
            # 超出容量时淘汰最久未使用的
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """手动删除某个缓存条目"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict:
        """返回缓存命中统计"""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / total * 100:.1f}%" if total > 0 else "N/A",
        }

    def __len__(self) -> int:
        return len(self._cache)


# ---- Redis-backed cache (optional) ----
class RedisCache:
    """Simple Redis-backed cache wrapper with pickle serialization.

    Keys in Redis are prefixed with project name to avoid collision.
    """

    def __init__(self, namespace: str = "aitutor", default_ttl: int = 1800, redis_url: str = None):
        self.namespace = namespace
        self.default_ttl = default_ttl
        self._client = None
        self._available = False
        try:
            import redis
            url = redis_url or os.getenv("REDIS_URL")
            if not url:
                raise ValueError("REDIS_URL not set")
            self._client = redis.from_url(url, decode_responses=False)
            # test
            self._client.ping()
            self._available = True
        except Exception as e:
            logger.info("RedisCache unavailable: %s", e)
            self._available = False

    def _key(self, key: str) -> str:
        return f"{self.namespace}:{key}"

    def get(self, key: str) -> Optional[Any]:
        if not self._available:
            return None
        try:
            val = self._client.get(self._key(key))
            if val is None:
                return None
            return pickle.loads(val)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        if not self._available:
            return None
        try:
            data = pickle.dumps(value)
            self._client.set(self._key(key), data, ex=ttl or self.default_ttl)
        except Exception:
            pass

    def invalidate(self, key: str) -> None:
        if not self._available:
            return None
        try:
            self._client.delete(self._key(key))
        except Exception:
            pass

    def clear(self) -> None:
        if not self._available:
            return None
        try:
            # delete keys by namespace
            pattern = f"{self.namespace}:*"
            cursor = '0'
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=1000)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0 or cursor == '0':
                    break
        except Exception:
            pass

    @property
    def stats(self) -> dict:
        if not self._available:
            return {"available": False}
        try:
            # approximate size by scanning
            count = 0
            cursor = '0'
            pattern = f"{self.namespace}:*"
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=1000)
                count += len(keys)
                if cursor == 0 or cursor == '0':
                    break
            return {"available": True, "size": count}
        except Exception:
            return {"available": False}


# ---- Helper to pick cache backend ----
def _select_cache(name: str, max_size: int = 1000, ttl_seconds: int = 1800):
    # If REDIS_URL defined, try RedisCache
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        rc = RedisCache(namespace=f"aitutor:{name}", default_ttl=ttl_seconds, redis_url=redis_url)
        if rc._available:
            return rc
    # fallback
    return TTLCache(max_size=max_size, ttl_seconds=ttl_seconds)


# ---- 预定义的缓存实例 ----

# 作业生成缓存：同学科同年级的作业直接复用（1 小时）
homework_cache = _select_cache("homework", max_size=500, ttl_seconds=3600)

# 作业批改缓存：相同作业+答案的批改结果（30 分钟）
review_cache = _select_cache("review", max_size=2000, ttl_seconds=1800)

# 深度解释缓存（30 分钟）
explain_cache = _select_cache("explain", max_size=1000, ttl_seconds=1800)

# 练习生成缓存（30 分钟）
practice_cache = _select_cache("practice", max_size=1000, ttl_seconds=1800)

# 科目提取缓存：相同输入的提取结果（24 小时，近似确定性）
subject_extraction_cache = _select_cache("subject_extraction", max_size=200, ttl_seconds=86400)

# 学生档案解析缓存（24 小时）
profile_parse_cache = _select_cache("profile_parse", max_size=200, ttl_seconds=86400)


def make_cache_key(*parts: str) -> str:
    """生成缓存键，对长内容做哈希以保持键短小

    Args:
        *parts: 参与键生成的各部分字符串

    Returns:
        缓存键字符串
    """
    raw = "|".join(str(p) for p in parts)
    # 短内容直接用作键，长内容做哈希
    if len(raw) <= 200:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class _CacheEntry:
    """缓存条目"""
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: float):
        self.value = value
        self.expires_at = expires_at


# ---- 预定义的缓存实例 ----

# 作业生成缓存：同学科同年级的作业直接复用（1 小时）
homework_cache = TTLCache(max_size=500, ttl_seconds=3600)

# 作业批改缓存：相同作业+答案的批改结果（30 分钟）
review_cache = TTLCache(max_size=2000, ttl_seconds=1800)

# 深度解释缓存（30 分钟）
explain_cache = TTLCache(max_size=1000, ttl_seconds=1800)

# 练习生成缓存（30 分钟）
practice_cache = TTLCache(max_size=1000, ttl_seconds=1800)

# 科目提取缓存：相同输入的提取结果（24 小时，近似确定性）
subject_extraction_cache = TTLCache(max_size=200, ttl_seconds=86400)

# 学生档案解析缓存（24 小时）
profile_parse_cache = TTLCache(max_size=200, ttl_seconds=86400)


def make_cache_key(*parts: str) -> str:
    """生成缓存键，对长内容做哈希以保持键短小

    Args:
        *parts: 参与键生成的各部分字符串

    Returns:
        缓存键字符串
    """
    raw = "|".join(str(p) for p in parts)
    # 短内容直接用作键，长内容做哈希
    if len(raw) <= 200:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
