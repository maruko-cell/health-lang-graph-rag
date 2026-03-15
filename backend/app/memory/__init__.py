"""
Memory 包：短期记忆（user_id + session_id）、长期记忆与用户画像（仅 user_id），均存 Redis。

功能描述：
对外提供统一接口：读短期/长期/画像用于拼 state；图结束后写短期并调用 updater 更新长期与画像。
"""

from app.memory.long_term import add_facts, get_long_memory, get_long_memory_context
from app.memory.profile import get_profile, update_profile
from app.memory.redis_client import get_redis
from app.memory.short_term import (
    append_turn,
    delete_session,
    get_full_history,
    get_short_memory,
    list_sessions,
)
from app.memory.updater import update_after_turn

__all__ = [
    "get_redis",
    "get_short_memory",
    "get_full_history",
    "append_turn",
    "delete_session",
    "list_sessions",
    "get_long_memory",
    "get_long_memory_context",
    "add_facts",
    "get_profile",
    "update_profile",
    "update_after_turn",
]
