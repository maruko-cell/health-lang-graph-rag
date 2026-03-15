from typing import AsyncGenerator

import asyncio
import json
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.state import GraphState
from app.nodes.query_rewrite import query_rewrite_node
from app.nodes.super import (
    build_super_graph,
    get_router_fn,
    get_subgraph_builders,
    get_summary_builder,
)
from app.memory import (
    get_short_memory,
    get_long_memory_context,
    get_profile,
    append_turn,
    update_after_turn,
)


"""
流式聊天路由模块，为前端提供基于文本分片的简单流式输出。

入参：
无全局入参，本模块通过路由函数接收请求体。

返回值：
无直接返回值，由 FastAPI 路由函数返回 StreamingResponse。

关键逻辑：
先按路由函数得到 route，再对当前分支子图 astream，最后 invoke summary，将 thinking / final_reply 增量以 JSONL 事件流返回，便于实时展示各子图节点状态。
"""


router = APIRouter(prefix="/chat/stream", tags=["chat"])
graph_app = build_super_graph()

_router_fn = get_router_fn()
_subgraph_builders = get_subgraph_builders()
_summary_builder = get_summary_builder()


class ChatStreamRequest(BaseModel):
    """
    流式聊天请求体模型。

    入参：
    - message：str，用户输入的聊天内容；
    - user_id：str，用户标识，用于长期记忆与画像；
    - session_id：str，会话标识，与 user_id 共同用于短期记忆；
    - image_path：str | None，可选，当前轮对话关联的已上传图片相对路径；
    - image_base64_url：str | None，可选，当前轮对话关联图片的 base64 Data URL；
    - image_url：str | None，可选，图片公网 URL（如 OSS 地址），优先于 image_base64_url 用于展示与多模态。

    返回值：
    无返回值，仅作为请求体验证与 IDE 类型提示模型使用。

    关键逻辑：
    允许在同一轮流式聊天请求中同时携带文本与图片路径，
    便于总图在路由阶段根据是否存在图片自动切换到多模态子图；
    agent_type 为 "selfie" 时强制走自画像子图（如前端点击 Self 按钮）；
    当提供 image_url 时，将同时写入 state 的 image_path 与 image_base64_url，供路由与多模态使用。
    """

    message: str
    user_id: str = "default_user"
    session_id: str = "default_session"
    image_path: str | None = None
    image_base64_url: str | None = None
    image_url: str | None = None
    agent_type: str | None = None


def _normalize_state(state: object) -> dict:
    """
    将图返回的 state 统一转为 dict，便于读取 thinking / final_reply。

    入参：state，图节点或流式 chunk 中的状态对象（可能是 dict、带 value 属性的对象等）。
    返回值：dict，保证为字典，无键时为空 dict。
    """
    if isinstance(state, dict):
        return state
    if state is None:
        return {}
    val = getattr(state, "value", state)
    if isinstance(val, dict):
        return val
    if hasattr(val, "items"):
        return dict(val)
    return {}


async def _chat_event_stream(init_state: GraphState, chunk_size: int = 40) -> AsyncGenerator[str, None]:
    """
    按路由选择子图后 astream 该子图，再 invoke summary，将 thinking / final_reply 增量按 chunk 以 JSONL 事件流返回。

    功能描述：
    - 用 get_router_fn() 得到 route，用 get_subgraph_builders() 取对应子图并 astream；
    - 每步 state 与已发送内容做差，按 chunk_size 推送 thinking_delta / answer_delta；
    - 子图结束后用 get_summary_builder() 得到 summary 图并 invoke，再推送 summary 的 thinking 与 final_reply。

    入参说明：
    - init_state：GraphState，本轮会话的初始图状态（含 query / image_path 等）；
    - chunk_size：int，每片推送的最大字符数。

    返回值说明：
    - AsyncGenerator[str, None]：逐行产出 JSON 字符串（每行一个事件，结尾换行）。
    """
    start_ts = time.time()
    last_sent_thinking = ""
    last_sent_reply = ""

    yield json.dumps({"type": "meta", "phase": "start"}, ensure_ascii=False) + "\n"

    subgraph_final_state: dict | None = None
    summary_state: dict | None = None

    try:
        route = _router_fn(init_state)
        chosen_builder = _subgraph_builders.get(route) or _subgraph_builders["default"]
        chosen_graph = chosen_builder()
        summary_graph = _summary_builder()

        try:
            stream = chosen_graph.astream(
                init_state,
                stream_mode="values",
                version="v2",
            )
        except TypeError:
            stream = chosen_graph.astream(init_state, stream_mode="values")

        async for chunk in stream:
            state = None
            if isinstance(chunk, dict):
                if chunk.get("type") == "values" and "data" in chunk:
                    state = _normalize_state(chunk["data"])
                elif "thinking" in chunk or "final_reply" in chunk:
                    state = _normalize_state(chunk)
            elif isinstance(chunk, (list, tuple)) and len(chunk) >= 2:
                state = _normalize_state(chunk[-1])
            elif isinstance(chunk, (list, tuple)) and len(chunk) == 1:
                state = _normalize_state(chunk[0])
            if not state:
                continue

            subgraph_final_state = state
            thinking = (state.get("thinking") or "").strip()
            reply = (state.get("final_reply") or "").strip()

            if thinking != last_sent_thinking:
                delta = thinking[len(last_sent_thinking) :] if thinking.startswith(last_sent_thinking) else thinking
                last_sent_thinking = thinking
                for i in range(0, len(delta), chunk_size):
                    piece = delta[i : i + chunk_size]
                    if not piece.strip():
                        continue
                    yield json.dumps({"type": "thinking_delta", "content": piece}, ensure_ascii=False) + "\n"
                    await asyncio.sleep(0.01)

            if reply != last_sent_reply:
                delta = reply[len(last_sent_reply) :] if reply.startswith(last_sent_reply) else reply
                last_sent_reply = reply
                for i in range(0, len(delta), chunk_size):
                    piece = delta[i : i + chunk_size]
                    if not piece.strip():
                        continue
                    yield json.dumps({"type": "answer_delta", "content": piece}, ensure_ascii=False) + "\n"
                    await asyncio.sleep(0.01)

        if subgraph_final_state is not None:
            summary_state = _normalize_state(summary_graph.invoke(subgraph_final_state))
            thinking = (summary_state.get("thinking") or "").strip()
            reply = (summary_state.get("final_reply") or "").strip()

            if thinking != last_sent_thinking:
                delta = thinking[len(last_sent_thinking) :] if thinking.startswith(last_sent_thinking) else thinking
                last_sent_thinking = thinking
                for i in range(0, len(delta), chunk_size):
                    piece = delta[i : i + chunk_size]
                    if not piece.strip():
                        continue
                    yield json.dumps({"type": "thinking_delta", "content": piece}, ensure_ascii=False) + "\n"
                    await asyncio.sleep(0.01)

            if reply != last_sent_reply:
                delta = reply[len(last_sent_reply) :] if reply.startswith(last_sent_reply) else reply
                last_sent_reply = reply
                for i in range(0, len(delta), chunk_size):
                    piece = delta[i : i + chunk_size]
                    if not piece.strip():
                        continue
                    yield json.dumps({"type": "answer_delta", "content": piece}, ensure_ascii=False) + "\n"
                    await asyncio.sleep(0.01)

    except Exception:
        pass

    if last_sent_thinking:
        yield json.dumps({"type": "thinking_done"}, ensure_ascii=False) + "\n"
    if last_sent_reply:
        yield json.dumps({"type": "answer_done"}, ensure_ascii=False) + "\n"

    user_id = (init_state.get("user_id") or "").strip() or "default_user"
    session_id = (init_state.get("session_id") or "").strip() or "default_session"
    user_message = (init_state.get("query") or "").strip()
    if user_id and session_id and user_message:
        append_turn(user_id, session_id, user_message, last_sent_reply)
        multi_moda = (summary_state or subgraph_final_state or {}).get("multi_moda_insight")
        update_after_turn(user_id, session_id, user_message, last_sent_reply, multi_moda)

    elapsed_ms = int((time.time() - start_ts) * 1000)
    yield json.dumps({"type": "meta", "phase": "end", "elapsed_ms": elapsed_ms}, ensure_ascii=False) + "\n"


@router.post("", response_class=StreamingResponse)
async def chat_stream(request: ChatStreamRequest) -> StreamingResponse:
    """
    流式聊天接口，用于为前端提供文本分片的流式输出。

    入参：
    request：ChatStreamRequest，请求体，包含 message、user_id、session_id 等。

    返回值：
    StreamingResponse：文本流式响应，响应体为分片后的纯文本数据流。

    关键逻辑：
    从 Redis 加载短期/长期记忆与用户画像填入 state，通过 _chat_event_stream 使用图 astream
    边执行边推送 thinking / final_reply 增量；流结束后写回短期记忆并触发长期记忆与画像更新。
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
    image_base64_url = (request.image_base64_url or "").strip() or None
    if request.image_path:
        init_state["image_path"] = request.image_path
    if image_url:
        init_state["image_path"] = init_state.get("image_path") or image_url
        init_state["image_base64_url"] = image_url
    elif image_base64_url:
        init_state["image_base64_url"] = image_base64_url
    if (request.agent_type or "").strip().lower() == "selfie":
        init_state["force_route"] = "selfie"

    # 流式路径不跑整图，在此先执行 query 重写，与非流式行为一致
    init_state = query_rewrite_node(init_state)

    return StreamingResponse(
        _chat_event_stream(init_state),
        media_type="application/jsonl; charset=utf-8",
    )
