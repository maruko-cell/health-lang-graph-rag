"""
向量化任务进度状态存储，供上传路由与 vectorize_and_store 任务共用。

功能描述：
在内存中维护 file_id -> { status, progress } 的映射，供前端轮询向量化进度；
存储与查询时对 file_id 做 Unicode NFC 规范化，避免中文等字符在 URL 编解码后 NFD/NFC 不一致导致 404。

入参/返回值：见各函数 docstring。
"""

from __future__ import annotations

import unicodedata
from typing import Any

# file_id -> { "status": "processing" | "done" | "failed", "progress": 0..100 }
_vectorization_status: dict[str, dict[str, Any]] = {}


def _normalize_file_id(file_id: str) -> str:
    """
    将 file_id 规范化为 NFC，便于与 URL 解码后的查询一致。

    入参：file_id：str，原始文件标识。
    返回值：str，NFC 规范化后的字符串。
    """
    return unicodedata.normalize("NFC", file_id)


def set_vectorization_status(
    file_id: str,
    status: str,
    progress: int = 0,
) -> None:
    """
    设置指定 file_id 的向量化状态与进度，供前端轮询。

    入参：
    - file_id：str，文件唯一标识；
    - status：str，应为 "processing" | "done" | "failed"；
    - progress：int，0–100 的进度百分比。

    返回值：无返回值。
    """
    key = _normalize_file_id(file_id)
    _vectorization_status[key] = {"status": status, "progress": min(100, max(0, progress))}


def get_vectorization_status(file_id: str) -> dict[str, Any] | None:
    """
    查询指定 file_id 的向量化状态，不存在则返回 None。

    入参：
    - file_id：str，文件唯一标识（路径参数，可能与存储时 Unicode 形式不同）。

    返回值：
    - dict[str, Any] | None：{ "status": str, "progress": int } 或 None。
    """
    key = _normalize_file_id(file_id)
    return _vectorization_status.get(key)
