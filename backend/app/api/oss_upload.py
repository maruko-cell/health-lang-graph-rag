"""
OSS 通用上传 API：通过 STS AssumeRole 获取临时凭证后上传字节流到 Bucket，并返回公网访问 URL。

入参：由调用方传入 data（bytes）、object_key、content_type；object_key 由调用方按业务前缀（如 OSS_IMAGE_PREFIX、OSS_FILE_PREFIX）自行拼接。
返回值：上传成功返回 dict，包含 url（全地址）、key、bucket。
关键逻辑：oss_sts.get_sts_credentials() -> StaticCredentialsProvider -> PutObject -> 构造公网 URL。
"""
from __future__ import annotations

import alibabacloud_oss_v2 as oss

from app.config import (
    OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET,
    OSS_BUCKET,
    OSS_REGION,
)

# 使用 STS 临时凭证创建 OSS 客户端
def _get_client() -> oss.Client:
    """
    使用 STS 临时凭证创建 OSS 客户端。
    入参：无入参，从 app.config 读取 OSS_*，通过 oss_sts.get_sts_credentials() 获取临时凭证。
    返回值：oss.Client。
    """
    from app.api.oss_sts import get_sts_credentials

    access_key_id, access_key_secret, security_token = get_sts_credentials()
    credentials_provider = oss.credentials.StaticCredentialsProvider(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        security_token=security_token or "",
    )
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = OSS_REGION
    return oss.Client(cfg)

# 构造公共读 Bucket 的公网访问 URL
def _public_url(bucket: str, region: str, key: str) -> str:
    """构造公共读 Bucket 的公网访问 URL。"""
    return f"https://{bucket}.oss-{region}.aliyuncs.com/{key}"

# 将二进制数据上传到 OSS 指定 object_key，并返回公网访问 URL
def upload_bytes(
    data: bytes,
    object_key: str,
    content_type: str = "application/octet-stream",
) -> dict[str, str]:
    """
    将二进制数据上传到 OSS 指定 object_key，并返回公网访问 URL。

    入参：
    - data：bytes，文件/图片二进制内容；
    - object_key：str，OSS 对象键（由调用方按 OSS_IMAGE_PREFIX / OSS_FILE_PREFIX 等拼接）；
    - content_type：str，MIME 类型。

    返回值：dict[str, str]，包含 url（全地址）、key、bucket。
    """
    bucket = OSS_BUCKET
    region = OSS_REGION
    if not bucket or not OSS_ACCESS_KEY_ID or not OSS_ACCESS_KEY_SECRET:
        raise ValueError(
            "OSS 配置不完整，请检查 OSS_BUCKET、OSS_ACCESS_KEY_ID、OSS_ACCESS_KEY_SECRET、OSS_STS_ROLE_ARN"
        )
    client = _get_client()
    request = oss.PutObjectRequest(bucket=bucket, key=object_key, body=data)
    client.put_object(request)
    url = _public_url(bucket, region, object_key)
    return {"url": url, "key": object_key, "bucket": bucket}
