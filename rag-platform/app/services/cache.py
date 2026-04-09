from __future__ import annotations

import hashlib
import json
import time
import uuid
from threading import Lock
from typing import Any

import redis

from app.config import get_settings

_MEMORY_CACHE: dict[str, tuple[float | None, str]] = {}
_MEMORY_COUNTERS: dict[str, tuple[float, int]] = {}
_LOCK = Lock()


def _client() -> redis.Redis | None:
    redis_url = get_settings().redis_url.strip()
    if not redis_url:
        return None
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def cache_get_json(key: str) -> Any | None:
    r = _client()
    if r is not None:
        raw = r.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    now = time.time()
    with _LOCK:
        item = _MEMORY_CACHE.get(key)
        if not item:
            return None
        expires_at, raw = item
        if expires_at is not None and expires_at <= now:
            _MEMORY_CACHE.pop(key, None)
            return None
    return json.loads(raw)


def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    r = _client()
    payload = json.dumps(value)
    if r is not None:
        r.setex(key, ttl_seconds, payload)
        return

    expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None
    with _LOCK:
        _MEMORY_CACHE[key] = (expires_at, payload)


def embedding_cache_key(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"emb:{h}"


def retrieval_cache_key(kb_id: uuid.UUID, query: str, hybrid: bool, top_k: int) -> str:
    qn = query.strip().lower()
    raw = f"{kb_id}:{hybrid}:{top_k}:{qn}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"ret:{h}"


def rate_limit_allow(ip: str, limit_per_minute: int) -> bool:
    if limit_per_minute <= 0:
        return True
    r = _client()
    if r is not None:
        from datetime import datetime

        bucket = datetime.utcnow().strftime("%Y%m%d%H%M")
        key = f"rl:{ip}:{bucket}"
        n = r.incr(key)
        if n == 1:
            r.expire(key, 70)
        return n <= limit_per_minute

    now = time.time()
    bucket = int(now // 60)
    key = f"rl:{ip}:{bucket}"
    with _LOCK:
        expires_at, count = _MEMORY_COUNTERS.get(key, (now + 70, 0))
        if expires_at <= now:
            expires_at, count = now + 70, 0
        count += 1
        _MEMORY_COUNTERS[key] = (expires_at, count)
        expired = [k for k, (ttl, _) in _MEMORY_COUNTERS.items() if ttl <= now]
        for expired_key in expired:
            _MEMORY_COUNTERS.pop(expired_key, None)
        return count <= limit_per_minute
