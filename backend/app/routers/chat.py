from fastapi import APIRouter
from pydantic import BaseModel

from app.state import GraphState
from app.nodes.super import build_super_graph
from app.memory import (
    get_short_memory,
    get_long_memory_context,
    get_profile,
    append_turn,
    update_after_turn,
)

router = APIRouter(prefix="/chat", tags=["chat"])
graph_app = build_super_graph()


class ChatRequest(BaseModel):
    """
    聊天请求体模型。

    入参：
    message：str，用户输入的聊天内容。
    user_id：str，用户标识，用于长期记忆与画像。
    session_id：str，会话标识，与 user_id 共同用于短期记忆。
    image_path：str | None，可选，当前轮关联的已上传图片路径。
    image_url：str | None，可选，图片公网 URL，优先用于多模态与展示。

    返回值：
    无返回值，仅作为请求体验证模型使用。

    关键逻辑：
    限定当前聊天接口的入参结构，便于后续扩展会话信息等字段；
    agent_type 为 "selfie" 时强制走自画像子图；
    提供 image_url 时会写入 state 的 image_path 与 image_base64_url。
    """

    message: str
    user_id: str = "default_user"
    session_id: str = "default_session"
    image_path: str | None = None
    image_url: str | None = None
    agent_type: str | None = None


class ChatResponse(BaseModel):
    """
    聊天响应体模型。

    入参：
    无入参，仅作为响应数据结构模型使用。

    返回值：
    reply：str，后端生成或返回的回复内容。

    关键逻辑：
    统一聊天接口的返回数据结构，后续可扩展为多字段（如引用信息、跟踪ID 等）。
    """

    reply: str


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    聊天接口，用于处理前端发送的自然语言提问。

    入参：
    request：ChatRequest，请求体，包含 message、user_id、session_id 等。

    返回值：
    ChatResponse：响应体，包含后端生成的 reply 字段。

    关键逻辑：
    从 Redis 加载短期/长期记忆与用户画像填入 state，调用总图 invoke，
    取 final_reply 后写回短期记忆并触发长期记忆与画像更新。
    """
    user_id = (request.user_id or "").strip() or "default_user"
    session_id = (request.session_id or "").strip() or "default_session"

    chat_history_short = get_short_memory(user_id, session_id)
    long_term_memory_context = get_long_memory_context(user_id)
    user_profile = get_profile(user_id)

    init_state: GraphState = {
        "query": request.message,
        "user_id": user_id,
        "session_id": session_id,
        "chat_history_short": chat_history_short,
        "long_term_memory_context": long_term_memory_context,
        "user_profile": user_profile,
    }
    image_url = (request.image_url or "").strip() or None
    if request.image_path:
        init_state["image_path"] = request.image_path
    if image_url:
        init_state["image_path"] = init_state.get("image_path") or image_url
        init_state["image_base64_url"] = image_url
    if (request.agent_type or "").strip().lower() == "selfie":
        init_state["force_route"] = "selfie"

    result: GraphState = graph_app.invoke(init_state)
    reply = result.get("final_reply", "图执行成功，但未生成最终回复内容 chat。")

    append_turn(user_id, session_id, request.message, reply)
    update_after_turn(
        user_id,
        session_id,
        request.message,
        reply,
        result.get("multi_moda_insight"),
    )

    return ChatResponse(reply=reply)

