"""
会话列表与聊天历史路由：按 user_id 查会话列表、按 (user_id, session_id) 查历史与删会话。
"""

from fastapi import APIRouter

from app.config import USER_ID
from app.memory import delete_session, get_full_history, list_sessions

router = APIRouter(tags=["sessions"])


@router.get("/memory/sessions")
async def get_sessions(user_id: str | None = None) -> list:
    """
    按 user_id 查询该用户的会话列表，按最后活动时间倒序。
    未传 user_id 时使用 config.USER_ID。
    """
    uid = (user_id or "").strip() or (USER_ID or "default_user")
    return list_sessions(uid)


@router.get("/chat/history")
async def get_chat_history(user_id: str | None = None, session_id: str | None = None) -> list:
    """
    按 user_id + session_id 查询该会话的全量聊天记录，供前端展示与刷新恢复。
    未传 user_id 时使用 config.USER_ID。
    """
    uid = (user_id or "").strip() or (USER_ID or "default_user")
    sid = (session_id or "").strip()
    if not sid:
        return []
    return get_full_history(uid, sid)


@router.delete("/chat/sessions")
async def delete_chat_session(user_id: str | None = None, session_id: str | None = None) -> dict:
    """
    按 user_id + session_id 删除该会话在 Redis 中的全部聊天数据及会话索引。
    未传 user_id 时使用 config.USER_ID。
    """
    uid = (user_id or "").strip() or (USER_ID or "default_user")
    sid = (session_id or "").strip()
    if not sid:
        return {"ok": False, "message": "session_id 必填"}
    delete_session(uid, sid)
    return {"ok": True}
