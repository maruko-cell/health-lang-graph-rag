"""
Memory Redis 键统一生成，供 short_term、long_term、profile 等模块使用。
"""


def short_key(user_id: str, session_id: str) -> str:
    """会话聊天记录 Redis 键：memory:short:{user_id}:{session_id}。"""
    return f"memory:short:{user_id}:{session_id}"


def sessions_key(user_id: str) -> str:
    """用户会话列表 Redis 键（Sorted Set）：memory:sessions:{user_id}。"""
    return f"memory:sessions:{user_id}"


def long_key(user_id: str) -> str:
    """长期记忆 Redis 键：memory:long:{user_id}。"""
    return f"memory:long:{user_id}"


def profile_key(user_id: str) -> str:
    """用户画像 Redis 键：memory:profile:{user_id}。"""
    return f"memory:profile:{user_id}"
