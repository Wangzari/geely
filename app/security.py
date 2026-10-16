"""调用方安全：API Key 鉴权（常量时间比较）+ 按 Key 滑动窗口限流。"""

from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException

from .config import get_settings


class SlidingWindowLimiter:
    """进程内滑动窗口限流。多 worker 部署时应换成 Redis 等共享存储。"""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()
            if len(bucket) >= self._max:
                return False
            bucket.append(now)
            return True


_settings = get_settings()
_limiter = SlidingWindowLimiter(_settings.service_rate_limit, 60)


def authenticate(x_api_key: str = Header(default="", alias="X-API-Key")) -> str:
    """校验调用方 API Key 并执行按 Key 限流。"""
    api_keys = _settings.api_keys
    if not api_keys:
        raise HTTPException(status_code=503, detail="服务未配置访问密钥")

    if not any(
        secrets.compare_digest(x_api_key.encode("utf-8"), key.encode("utf-8"))
        for key in api_keys
    ):
        raise HTTPException(status_code=401, detail="无效的 API Key")

    if not _limiter.allow(x_api_key):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
    return x_api_key


def ensure_vehicle_allowed(vehicle_code: str) -> None:
    """车辆白名单校验；越权统一返回 404，不暴露差异。"""
    if vehicle_code not in _settings.allowed_vehicles:
        raise HTTPException(status_code=404, detail="未找到该车辆")
