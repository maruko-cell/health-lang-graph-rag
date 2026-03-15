"""
知识库上传登记：按 user_id 将 file_id 与 url 等信息写入 Redis，支持查询历史。

功能描述：
使用 Redis Hash 存储，key 为 kb_uploads:{user_id}，field 为 file_id，value 为 JSON（url、filename、uploaded_at）。
同一 file_id 再次写入会覆盖，便于「内容 hash 去重」场景。

入参/返回值：见各函数 docstring。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.memory.redis_client import get_redis

REDIS_KB_UPLOADS_PREFIX = "kb_uploads:"


def _key(user_id: str) -> str:
    """生成对应用户的 Redis key。"""
    return f"{REDIS_KB_UPLOADS_PREFIX}{user_id}"


def save_kb_upload(
    user_id: str,
    file_id: str,
    url: str,
    filename: str,
) -> None:
    """
    将一次知识库上传记录写入 Redis（按 user_id 维度，file_id 为 field）。

    入参：
    - user_id：str，用户标识；
    - file_id：str，文件内容哈希（如 SHA256 前 16 位）；
    - url：str，文件公网 URL（如 OSS 地址）；
    - filename：str，原始文件名。

    返回值：无返回值；Redis 未配置或写入失败时静默跳过。
    """
    client = get_redis()
    if not client:
        return
    try:
        payload: dict[str, Any] = {
            "url": url,
            "filename": filename,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        client.hset(_key(user_id), file_id, json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


def list_kb_uploads(user_id: str) -> list[dict[str, Any]]:
    """
    查询某用户已登记的知识库上传列表（file_id、url、filename、uploaded_at）。

    入参：
    - user_id：str，用户标识。

    返回值：list[dict]，每项包含 file_id、url、filename、uploaded_at；Redis 未配置或异常时返回空列表。
    """
    client = get_redis()
    if not client:
        return []
    try:
        key = _key(user_id)
        raw = client.hgetall(key)
        if not raw:
            return []
        out: list[dict[str, Any]] = []
        for fid, val in raw.items():
            try:
                data = json.loads(val) if isinstance(val, str) else val
                out.append({
                    "file_id": fid,
                    "url": data.get("url", ""),
                    "filename": data.get("filename", ""),
                    "uploaded_at": data.get("uploaded_at", ""),
                })
            except (TypeError, json.JSONDecodeError):
                continue
        out.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
        return out
    except Exception:
        return []
