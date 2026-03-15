"""
知识库文件上传路由模块，为前端提供 PDF、Word、纯文本等文件上传及向量化入库能力。

入参：
无全局入参，具体由路由函数接收 multipart/form-data 上传的文件字段。

返回值：
无直接返回值，由 FastAPI 路由函数返回 JSON 响应。

关键逻辑：
从 .env 中读取允许的知识库文件 MIME 类型常量（KB_ALLOWED_TYPES），对上传文件进行校验；
OSS 上传使用文件内容哈希作为 file_id，并按 user_id 将 file_id 与 url 登记到 Redis，支持查询。
"""
from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Header, HTTPException, UploadFile

from app.api.kb_upload_registry import list_kb_uploads, save_kb_upload
from app.api.oss_upload import upload_bytes as oss_upload_bytes
from app.config import KB_ALLOWED_TYPES, OSS_FILE_PREFIX
from app.tasks import add_task, vectorize_and_store
from app.tasks.vectorization_status import get_vectorization_status, set_vectorization_status

router = APIRouter(prefix="/upload", tags=["upload"])
_KB_ALLOWED_TYPES = {t.strip() for t in (KB_ALLOWED_TYPES or "").split(",") if t.strip()}


@router.post("/kb-file")
async def upload_kb_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> dict[str, str]:
    """
    知识库文件上传到阿里云 OSS，返回可下载 URL；按内容哈希生成 file_id，登记到 Redis 后按 URL 向量化入库。

    入参：file（UploadFile）、background_tasks（BackgroundTasks）、X-User-Id（Header，必填）。
    返回值：dict，包含 filename、content_type、path（OSS 公网 URL）、file_id、status、url（同上）。
    关键逻辑：类型校验 → 读取 content → file_id=sha256(content)[:16] → OSS 上传 → Redis 登记 → 提交 vectorize_and_store。
    """
    if not (x_user_id and x_user_id.strip()):
        raise HTTPException(status_code=400, detail="请提供 X-User-Id 请求头")
    user_id = x_user_id.strip()

    if _KB_ALLOWED_TYPES and file.content_type not in _KB_ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的知识库文件类型：{file.content_type}")

    content = await file.read()
    file_id = hashlib.sha256(content).hexdigest()[:16]
    content_type = file.content_type or "application/octet-stream"
    prefix = (OSS_FILE_PREFIX or "files/").rstrip("/") + "/"
    safe_name = f"{uuid4().hex}_{file.filename}"
    object_key = f"{prefix}{safe_name}"

    try:
        result = oss_upload_bytes(data=content, object_key=object_key, content_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OSS 上传失败：{e}") from e

    url = result["url"]
    save_kb_upload(user_id=user_id, file_id=file_id, url=url, filename=file.filename or "file")
    set_vectorization_status(file_id, "processing", 0)
    add_task(background_tasks, vectorize_and_store, url=url, file_id=file_id)

    return {
        "filename": file.filename or "file",
        "content_type": content_type,
        "path": url,
        "file_id": file_id,
        "status": "processing",
        "url": url,
    }


@router.get("/kb-file")
async def list_user_kb_uploads(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> list[dict[str, str]]:
    """
    按用户查询已上传的知识库文件列表（file_id、url、filename、uploaded_at），从 Redis 读取。

    入参：X-User-Id（Header，必填）。
    返回值：list[dict]，每项含 file_id、url、filename、uploaded_at；未提供 user_id 时 400。
    """
    if not (x_user_id and x_user_id.strip()):
        raise HTTPException(status_code=400, detail="请提供 X-User-Id 请求头")
    return list_kb_uploads(x_user_id.strip())


@router.get("/kb-file/{file_id}/status")
async def get_kb_file_status(file_id: str) -> dict[str, str | int]:
    """
    查询知识库文件向量化任务状态与进度，供前端轮询。

    入参：
    - file_id：str，上传接口返回的文件唯一标识（路径参数）。

    返回值：
    - dict：{ "status": "processing" | "done" | "failed", "progress": 0..100 }；
      若 file_id 不存在则 404。

    关键逻辑：
    从内存存储读取 vectorization_status，不存在则返回 404。
    """
    status = get_vectorization_status(file_id)
    if status is None:
        raise HTTPException(status_code=404, detail="未找到该文件的向量化状态")
    return status
