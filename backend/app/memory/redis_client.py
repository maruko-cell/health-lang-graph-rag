"""
Redis 客户端模块：懒加载单例，从 config.REDIS_URL 连接；未配置或连接失败返回 None，各 memory 子模块无 client 时 no-op。
"""

from __future__ import annotations

from typing import Any, Optional

_client: Optional[Any] = None


def get_redis():  # -> Optional[redis.Redis]，避免顶层 import redis 未安装时报错
    """
    返回全局 Redis 客户端单例；未配置或连接失败时返回 None。
    入参：无。
    返回值：redis.Redis 或 None。
    关键逻辑：懒加载，首次调用时 from_url(REDIS_URL) 并 ping，失败则置 None。
    """
    global _client
    if _client is not None:
        return _client
    from app.config import REDIS_URL
    if not (REDIS_URL and str(REDIS_URL).strip()):
        return None
    try:
        import redis
        _client = redis.from_url(REDIS_URL, decode_responses=True)
        _client.ping()
        return _client
    except Exception:
        _client = None
        return None
