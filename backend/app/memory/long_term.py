"""
长期记忆模块：按用户（仅 user_id）存储多会话总结的事实列表，使用 Redis String(JSON)。

功能描述：
facts 列表项含 text、type、source、ts；支持 get、add_facts、拼成「已知用户信息」上下文字符串。
无 Redis 时读返回 []/空串，写 no-op。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from app.memory.keys import long_key
from app.memory.redis_client import get_redis

# 读取该用户的长期事实列表。
def get_long_memory(user_id: str) -> List[Dict[str, Any]]:
    """
    读取该用户的长期事实列表。

    入参：user_id，str，用户标识。
    返回值：list[dict]，每项含 text、type、source、ts 等；无则 []。
    关键逻辑：GET key 解析 JSON 取 facts；无 client 返回 []。
    """
    client = get_redis()
    if client is None:
        return []
    try:
        raw = client.get(long_key(user_id))
        if not raw:
            return []
        data = json.loads(raw)
        return data.get("facts") if isinstance(data.get("facts"), list) else []
    except (json.JSONDecodeError, TypeError, Exception):
        return []

# 将长期事实拼成「已知用户信息：……」字符串，供注入 state。
def get_long_memory_context(user_id: str, max_facts: Optional[int] = 50) -> str:
    """
    将长期事实拼成「已知用户信息：……」字符串，供注入 state。

    入参：
    - user_id：str，用户标识。
    - max_facts：int | None，最多取前几条；None 表示不限制。

    返回值：str，无事实时返回空串。
    关键逻辑：get_long_memory 后截断 max_facts，逐条取 text 拼成一行或短段。
    """
    facts = get_long_memory(user_id)
    if not facts:
        return ""
    if max_facts is not None:
        facts = facts[:max_facts]
    lines = []
    for f in facts:
        if isinstance(f, dict) and f.get("text"):
            lines.append(f.get("text", "").strip())
    if not lines:
        return ""
    return "已知用户信息：\n" + "\n".join(lines)

# 将新事实追加到该用户长期记忆并写回 Redis。
def add_facts(
    user_id: str,
    new_facts: List[Dict[str, Any]],
    source: str = "",
) -> None:
    """
    将新事实追加到该用户长期记忆并写回 Redis。

    入参：
    - user_id：str，用户标识。
    - new_facts：list[dict]，每项建议含 text、type、source、ts。
    - source：str，来源标识（如 session_id）。

    返回值：无返回值。
    关键逻辑：GET 当前 JSON → 解析 facts → 追加 new_facts（简单按 text 去重）→ SET，更新 updated_at。无 client 则 return。
    """
    if not new_facts:
        return
    client = get_redis()
    if client is None:
        return
    key = long_key(user_id)
    ts = int(time.time())
    existing: List[Dict[str, Any]] = []
    try:
        raw = client.get(key)
        if raw:
            data = json.loads(raw)
            if isinstance(data.get("facts"), list):
                existing = list(data.get("facts", []))
    except (json.JSONDecodeError, TypeError):
        pass
    seen_texts = {str(f.get("text", "")).strip() for f in existing if isinstance(f, dict) and f.get("text")}
    for f in new_facts:
        if not isinstance(f, dict):
            continue
        text = (f.get("text") or "").strip()
        if not text or text in seen_texts:
            continue
        seen_texts.add(text)
        existing.append({
            "text": text,
            "type": f.get("type", ""),
            "source": f.get("source", source),
            "ts": f.get("ts", ts),
        })
    payload = {"facts": existing, "updated_at": ts}
    try:
        client.set(key, json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass
