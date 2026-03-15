"""
当前用户占位路由：返回 .env 中的 USER_ID，后续登录改为从 token 解析。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import USER_ID

router = APIRouter(prefix="/user", tags=["user"])


class CurrentUserResponse(BaseModel):
    """当前用户响应：user_id 占位，后续接登录后从 token 解析。"""
    user_id: str


@router.get("/current", response_model=CurrentUserResponse)
async def get_current_user() -> CurrentUserResponse:
    """
    返回当前用户 id；当前从 .env USER_ID 读取，后续登录后改为从 token 解析。
    """
    return CurrentUserResponse(user_id=USER_ID or "default_user")
