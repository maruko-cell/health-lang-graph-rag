"""
短期记忆模块：按会话（user_id + session_id）存储最近 N 轮对话，使用 Redis List。

功能描述：
每轮两条元素（user / assistant），LRANGE 取最近 2*N 条作为短期上下文；
RPUSH 追加本轮，可选 TTL。无 Redis 时读返回 []、写 no-op。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from app.config import SHORT_TERM_MEMORY_MAX_TURNS, SHORT_TERM_MEMORY_TTL
from app.memory.keys import sessions_key, short_key
from app.memory.redis_client import get_redis

# 读取该会话最近 N 轮对话，用于拼入图状态。
def get_short_memory(
    user_id: str,
    session_id: str,
    last_n_turns: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    读取该会话最近 N 轮对话，用于拼入图状态。

    入参：
    - user_id：str，用户标识。
    - session_id：str，会话标识。
    - last_n_turns：int | None，参与上下文的轮数；None 时使用 config.SHORT_TERM_MEMORY_MAX_TURNS。

    返回值：
    list[dict]：元素为 {"role":"user"|"assistant","content":"...","ts":...}，按时间正序。

    关键逻辑：LRANGE key -(2*N) -1，逐条 JSON 解析；无 client 返回 []。
    """
    client = get_redis()
    if client is None:
        return []
    n = last_n_turns if last_n_turns is not None else (SHORT_TERM_MEMORY_MAX_TURNS or 20)
    key = short_key(user_id, session_id)
    try:
        raw_list = client.lrange(key, -(2 * n), -1)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for s in raw_list or []:
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except (json.JSONDecodeError, TypeError):
            continue
    return out

# 将本轮用户消息与助手回复追加到该会话短期记忆。
def append_turn(
    user_id: str,
    session_id: str,
    user_content: str,
    assistant_content: str,
) -> None:
    """
    将本轮用户消息与助手回复追加到该会话短期记忆。

    入参：
    - user_id：str，用户标识。
    - session_id：str，会话标识。
    - user_content：str，用户本条消息。
    - assistant_content：str，助手本条回复。

    返回值：无返回值。
    关键逻辑：RPUSH 两条 JSON；若配置了 SHORT_TERM_MEMORY_TTL 则对该 key 设置 TTL（秒）。无 client 则 return。
    """
    client = get_redis()
    if client is None:
        return
    key = short_key(user_id, session_id)
    ts = int(time.time())
    user_item = {"role": "user", "content": user_content or "", "ts": ts}
    assistant_item = {"role": "assistant", "content": assistant_content or "", "ts": ts}
    try:
        client.rpush(key, json.dumps(user_item, ensure_ascii=False), json.dumps(assistant_item, ensure_ascii=False))
        if SHORT_TERM_MEMORY_TTL is not None and SHORT_TERM_MEMORY_TTL > 0:
            client.expire(key, SHORT_TERM_MEMORY_TTL)
        # 维护用户会话列表索引：该会话最后活动时间
        skey = sessions_key(user_id)
        client.zadd(skey, {session_id: ts})
    except Exception:
        pass

# 读取该会话的全量聊天记录，供前端展示与刷新恢复。
def get_full_history(user_id: str, session_id: str) -> List[Dict[str, Any]]:
    """
    读取该会话的全量聊天记录，供前端展示与刷新恢复。

    入参：
    - user_id：str，用户标识。
    - session_id：str，会话标识。

    返回值：
    list[dict]：元素为 {"role":"user"|"assistant","content":"...","ts":...}，按时间正序。

    关键逻辑：LRANGE key 0 -1 全量返回；无 client 或 key 不存在返回 []。
    """
    client = get_redis()
    if client is None:
        return []
    key = short_key(user_id, session_id)
    try:
        raw_list = client.lrange(key, 0, -1)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for s in raw_list or []:
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except (json.JSONDecodeError, TypeError):
            continue
    return out

# 删除该会话在 Redis 中的全部聊天数据及会话索引中的记录。
def delete_session(user_id: str, session_id: str) -> None:
    """
    删除该会话在 Redis 中的全部聊天数据及会话索引中的记录。

    入参：
    - user_id：str，用户标识。
    - session_id：str，会话标识。

    返回值：无返回值。
    关键逻辑：DEL 会话 key；ZREM 从 memory:sessions:{user_id} 中移除 session_id。无 client 则 return。
    """
    client = get_redis()
    if client is None:
        return
    key = short_key(user_id, session_id)
    skey = sessions_key(user_id)
    try:
        client.delete(key)
        client.zrem(skey, session_id)
    except Exception:
        pass

# 按 user_id 查询会话列表，按最后活动时间倒序。
def list_sessions(user_id: str) -> List[Dict[str, Any]]:
    """
    按 user_id 查询会话列表，按最后活动时间倒序。

    入参：
    - user_id：str，用户标识。

    返回值：
    list[dict]：元素含 session_id、last_activity_ts；可选 title（首条用户消息前 20 字或「新会话」）。

    关键逻辑：ZREVRANGE memory:sessions:{user_id} 0 -1 WITHSCORES；无 client 返回 []。
    """
    client = get_redis()
    if client is None:
        return []
    skey = sessions_key(user_id)
    try:
        raw = client.zrevrange(skey, 0, -1, withscores=True)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for session_id, score in raw or []:
        if not session_id:
            continue
        item: Dict[str, Any] = {"session_id": session_id, "last_activity_ts": int(float(score))}
        # 可选：从首条消息取 title
        key = short_key(user_id, session_id)
        try:
            first_user = None
            for s in client.lrange(key, 0, -1) or []:
                try:
                    obj = json.loads(s)
                    if obj.get("role") == "user" and obj.get("content"):
                        first_user = (obj.get("content") or "").strip()[:20]
                        break
                except (json.JSONDecodeError, TypeError):
                    continue
            item["title"] = first_user or "新会话"
        except Exception:
            item["title"] = "新会话"
        out.append(item)
    return out
