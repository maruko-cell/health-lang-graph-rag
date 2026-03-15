"""
MCP HTTP 客户端公共封装。

本模块对外提供 call_mcp_http() 作为统一的 MCP HTTP 调用入口；
使用 urllib 发起请求，统一处理超时、编码与错误信息，便于上层节点复用。
"""

from __future__ import annotations

import json
from typing import Any, Mapping, MutableMapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def call_mcp_http(
    url: str,
    *,
    payload: Optional[Mapping[str, Any]] = None,
    timeout: Optional[int] = None,
    method: str = "POST",
    headers: Optional[Mapping[str, str]] = None,
    ensure_ascii: bool = False,
) -> str:
    """
    统一封装 MCP HTTP 服务调用，输入 MCP URL 输出响应文本。

    入参：
    - url：str，MCP HTTP 服务地址（例如 .env 中的 AMAP_MCP_URL）。
    - payload：Mapping[str, Any] | None，请求体 JSON 对象；为 None 时不携带 body。
    - timeout：int | None，超时秒数；为 None 时沿用 urllib 默认超时策略。
    - method：str，HTTP 方法，默认 "POST"。
    - headers：Mapping[str, str] | None，额外请求头；会与默认头合并，入参优先。
    - ensure_ascii：bool，JSON 序列化是否强制 ASCII 转义；默认 False，便于中文直读。

    返回值：
    str：服务端响应文本（按 UTF-8 解码）。

    关键逻辑：
    - 默认设置 Content-Type 为 application/json，Accept 支持 JSON 与 SSE；
    - 统一捕获 HTTPError / URLError / 其他异常，转换为 RuntimeError 抛出。
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("MCP URL 不能为空")

    merged_headers: MutableMapping[str, str] = {
        "Connection": "keep-alive",
    }
    if payload is not None:
        merged_headers.setdefault("Content-Type", "application/json; charset=utf-8")
        merged_headers.setdefault("Accept", "application/json, text/event-stream, text/plain, */*")
    if headers:
        merged_headers.update(dict(headers))

    data = json.dumps(payload, ensure_ascii=ensure_ascii).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, headers=dict(merged_headers), method=(method or "POST").upper())

    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        msg = f"HTTP {getattr(exc, 'code', 'UNKNOWN')}：{getattr(exc, 'reason', '')}"
        if body:
            msg = f"{msg}，响应：{body}"
        raise RuntimeError(f"调用 MCP HTTP 失败：{msg}") from exc
    except URLError as exc:
        raise RuntimeError(f"调用 MCP HTTP 失败：网络错误 {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"调用 MCP HTTP 失败：{exc}") from exc
