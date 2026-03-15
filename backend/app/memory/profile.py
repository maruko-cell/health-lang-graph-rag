"""
用户画像模块：按用户（仅 user_id）存储结构化画像，使用 Redis String(JSON)。

功能描述：
与 exercise 等子图使用的 user_profile 结构一致（age、gender、height_cm、weight_kg、
chronic_diseases 等）；支持 get、update_profile 深合并。无 Redis 时读返回空 dict，写 no-op。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

from app.memory.keys import profile_key
from app.memory.redis_client import get_redis

# 返回与 exercise 子图一致的默认画像结构。
def _default_profile() -> Dict[str, Any]:
    """返回与 exercise 子图一致的默认画像结构。"""
    return {
        # 年龄（岁）
        "age": None,
        # 性别
        "gender": None,
        # 身高（厘米）
        "height_cm": None,
        # 体重（公斤）
        "weight_kg": None,
        # 慢性病/基础疾病列表
        "chronic_diseases": [],
        # 过敏史/过敏原列表
        "allergies": [],
        # 当前用药列表
        "medications": [],
        # 画像最后更新时间（时间戳或 ISO 字符串）
        "updated_at": None,
    }

# 读取该用户的画像；无则返回默认空结构。
def get_profile(user_id: str) -> Dict[str, Any]:
    """
    读取该用户的画像；无则返回默认空结构。

    入参：user_id，str，用户标识。
    返回值：dict，与 exercise user_profile 结构一致。
    关键逻辑：GET key 解析 JSON；无 client 返回 _default_profile()。
    """
    client = get_redis()
    if client is None:
        return _default_profile()
    try:
        raw = client.get(profile_key(user_id))
        if not raw:
            return _default_profile()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return _default_profile()
        out = _default_profile()
        for k in out:
            if k in data:
                out[k] = data[k]
        return out
    except (json.JSONDecodeError, TypeError, Exception):
        return _default_profile()

# 更新用户画像；将部分画像字段与现有画像深合并后写回 Redis。
def update_profile(user_id: str, partial: Dict[str, Any]) -> None:
    """
    将部分画像字段与现有画像深合并后写回 Redis。

    入参：
    - user_id：str，用户标识。
    - partial：dict，本次要合并的字段（如 age、chronic_diseases）；列表类字段做合并去重。

    返回值：无返回值。
    关键逻辑：GET 当前 profile → 深合并（列表 extend 去重）→ SET，写 updated_at。无 client 则 return。
    """
    if not partial:
        return
    client = get_redis()
    if client is None:
        return
    key = profile_key(user_id)
    current = get_profile(user_id)
    list_keys = ("chronic_diseases", "allergies", "medications")
    # 遍历部分画像字段，与现有画像深合并。
    for k, v in partial.items():
        if v is None:
            continue
        if k in list_keys and isinstance(v, list):
            base = current.get(k) or []
            if isinstance(base, list):
                current[k] = list(dict.fromkeys(base + [x for x in v if x]))
            else:
                current[k] = list(dict.fromkeys(v))
        elif isinstance(v, (dict, list)):
            current[k] = v
        else:
            current[k] = v
    current["updated_at"] = int(time.time())
    try:
        client.set(key, json.dumps(current, ensure_ascii=False))
    except Exception:
        pass
