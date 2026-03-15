"""
通过 STS AssumeRole 获取临时凭证，供 OSS 等服务使用。

入参：从 app.config 读取 OSS_ACCESS_KEY_ID、OSS_ACCESS_KEY_SECRET（调用者 RAM 用户）、
     OSS_STS_ROLE_ARN、OSS_STS_ROLE_SESSION_NAME、OSS_STS_ENDPOINT、OSS_STS_DURATION_SECONDS。
返回值：tuple[str, str, str]，(access_key_id, access_key_secret, security_token)。
关键逻辑：使用 alibabacloud_sts20150401 调用 AssumeRole，并在有效期内缓存凭证以减少调用频率。
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Tuple

from app.config import (
    OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET,
    OSS_REGION,
    OSS_STS_DURATION_SECONDS,
    OSS_STS_ENDPOINT,
    OSS_STS_ROLE_ARN,
    OSS_STS_ROLE_SESSION_NAME,
)

# 缓存：临时凭证及过期时间；在过期前 5 分钟即刷新
_cached: Tuple[str, str, str] | None = None
_cached_expiration: datetime | None = None
_cache_lock = threading.Lock()
_REFRESH_BEFORE_SECONDS = 300

# 将 AssumeRole 返回的 Expiration（ISO8601）解析为 datetime
def _parse_expiration(expiration_str: str) -> datetime:
    """
    将 AssumeRole 返回的 Expiration（ISO8601）解析为 datetime。

    入参：expiration_str（str），如 2025-03-14T12:00:00Z。
    返回值：datetime，带 UTC 时区。
    """
    return datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))

def get_sts_credentials() -> Tuple[str, str, str]:
    """
    调用 STS AssumeRole 获取临时凭证；若缓存未过期则直接返回缓存。

    入参：无入参，从 app.config 读取 OSS_* 与 OSS_STS_* 配置。
    返回值：tuple[str, str, str]，(access_key_id, access_key_secret, security_token)。
    关键逻辑：使用 RAM 用户 AK/SK 创建 STS 客户端，调用 AssumeRole，解析 body.credentials；
             若已缓存且未到刷新时间则返回缓存，否则重新请求并更新缓存；配置或 API 异常由调用方或 SDK 抛出，解析失败时兜底 RuntimeError。
    """
    global _cached, _cached_expiration

    with _cache_lock:
        now = datetime.now(timezone.utc)
        if _cached is not None and _cached_expiration is not None:
            exp = _cached_expiration if _cached_expiration.tzinfo else _cached_expiration.replace(tzinfo=timezone.utc)
            if now + timedelta(seconds=_REFRESH_BEFORE_SECONDS) < exp:
                return _cached

    from alibabacloud_sts20150401.client import Client as StsClient
    from alibabacloud_sts20150401 import models as sts_models
    from alibabacloud_tea_openapi import models as open_api_models
    # 创建STS客户端配置
    config = open_api_models.Config(
        access_key_id=OSS_ACCESS_KEY_ID,
        access_key_secret=OSS_ACCESS_KEY_SECRET,
        region_id=OSS_REGION,
        endpoint=OSS_STS_ENDPOINT,
    )
    sts_client = StsClient(config)
    request = sts_models.AssumeRoleRequest(
        role_arn=OSS_STS_ROLE_ARN,
        role_session_name=OSS_STS_ROLE_SESSION_NAME,
        duration_seconds=OSS_STS_DURATION_SECONDS,
    )
    response = sts_client.assume_role(request)
    creds = response.body.credentials

    # SDK 可能返回 PascalCase 或 snake_case，兼容两种命名
    access_key_id = getattr(creds, "AccessKeyId", None) or getattr(creds, "access_key_id", None)
    access_key_secret = getattr(creds, "AccessKeySecret", None) or getattr(creds, "access_key_secret", None)
    security_token = getattr(creds, "SecurityToken", None) or getattr(creds, "security_token", None)
    expiration_str = getattr(creds, "expiration", None) or getattr(creds, "Expiration", None)

    if not access_key_id or not access_key_secret or not security_token:
        raise RuntimeError("STS 获取临时凭证失败，返回凭证不完整")

    result = (access_key_id, access_key_secret, security_token)
    with _cache_lock:
        _cached = result
        _cached_expiration = _parse_expiration(expiration_str) if expiration_str else None

    return result
