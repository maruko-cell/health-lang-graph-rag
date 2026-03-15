"""
图片上传路由模块：接收前端图片文件并上传至阿里云 OSS，返回公网可访问的 URL。
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.oss_upload import upload_bytes
from app.config import IMAGE_ALLOWED_TYPES, OSS_IMAGE_PREFIX

router = APIRouter(prefix="/upload", tags=["upload"])
_ALLOWED_TYPES = {t.strip() for t in (IMAGE_ALLOWED_TYPES or "").split(",") if t.strip()}


@router.post("/image/oss")
async def upload_image_to_oss(file: UploadFile = File(...)) -> dict[str, str]:
    """
    上传图片到阿里云 OSS，返回可访问的 URL。
    入参：file（UploadFile）。返回值：url（全地址）、filename、content_type。
    关键逻辑：类型校验 → 按 OSS_IMAGE_PREFIX 拼 object_key → upload_bytes 上传并返回 url。
    """
    if _ALLOWED_TYPES and file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的图片类型：{file.content_type}")

    data = await file.read()
    content_type = file.content_type or "image/jpeg"
    prefix = (OSS_IMAGE_PREFIX or "images/").rstrip("/") + "/"
    safe_name = file.filename if file.filename else "image.jpg"
    object_key = f"{prefix}{uuid4().hex}_{safe_name}"

    try:
        result = upload_bytes(data=data, object_key=object_key, content_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OSS 上传失败：{e}") from e

    return {
        "url": result["url"],
        "filename": file.filename,
        "content_type": content_type,
    }
