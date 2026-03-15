"""
异常兜底（DefaultHandler）子图模块。

入参：
无入参，本模块提供子图构建函数 build_default_handler_graph() 供总图调用。

返回值：
通过 build_default_handler_graph() 返回编译后的子图（CompiledStateGraph）。

关键逻辑：
当前用于统一处理异常或兜底场景；若存在长期记忆且用户问题为身份/回忆类（如「我是谁」），
则根据长期记忆生成回复，否则从 fallback.json 中随机选取一条友好文案回复用户，并写入 final_reply。
"""

import json
import random
import re
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.common.Prompt import IDENTITY_HUMAN_TEMPLATE, IDENTITY_SYSTEM
from app.common.prompt_utils import build_system_human_messages
from app.common.thinkings import DEFAULT_THINKING_BASE, DEFAULT_THINKING_ERROR_SUFFIX
from app.state import GraphState
from app.nodes.default_handler_state import DefaultHandlerState

# 兜底文案配置文件路径（backend/common/fallback.json）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_FALLBACK_PATH = _BACKEND_ROOT / "common" / "fallback.json"

# 从 fallback.json 读取兜底回复文案列表
def _load_fallback_messages() -> list[str]:
    try:
        with open(_FALLBACK_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        messages = data.get("fallback") or []
        if isinstance(messages, list) and len(messages) > 0:
            return messages
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return ["当前服务暂时无法处理该问题，请稍后重试或换个健康相关的问题问我哦～"]


_FALLBACK_MESSAGES: list[str] = _load_fallback_messages()

def _is_identity_like_query(query: str) -> bool:
    """
    判断用户问题是否为身份/回忆类（如「我是谁」「我叫什么」），以便用长期记忆回答。

    入参：query，str，用户输入。
    返回值：bool，True 表示疑似身份类问题。
    """
    q = (query or "").strip()
    if not q or len(q) > 100:
        return False
    patterns = [
        r"我\s*是\s*谁",
        r"我\s*叫\s*什么",
        r"你\s*知道\s*我\s*是\s*谁",
        r"我\s*叫\s*啥",
        r"我\s*的\s*名字",
        r"你\s*记\s*得\s*我",
        r"我\s*是\s*啥",
    ]
    return bool(re.search("|".join(patterns), q, re.IGNORECASE))


# 异常兜底子图内核心节点
def _default_handler_node(state: DefaultHandlerState) -> DefaultHandlerState:

    # 更新状态
    new_state: DefaultHandlerState = dict(state)
    raw_error = (new_state.get("error_message") or "").strip()
    query = (new_state.get("query") or "").strip()
    memory_context = (new_state.get("long_term_memory_context") or "").strip()

    # 标记该子图已执行
    new_state["error_placeholder"] = "default_handler"

    user_msg: str
    if memory_context and _is_identity_like_query(query):
        try:
            from app.llm_agent.agent import create_llm_agent
            cfg = create_llm_agent()
            human_content = IDENTITY_HUMAN_TEMPLATE.format(memory_context=memory_context, query=query)
            messages = build_system_human_messages(IDENTITY_SYSTEM, human_content)
            user_msg = cfg.invoke_and_get_content(messages, default=random.choice(_FALLBACK_MESSAGES))
        except Exception:
            user_msg = random.choice(_FALLBACK_MESSAGES)
    else:
        user_msg = random.choice(_FALLBACK_MESSAGES)

    new_state["user_friendly_error"] = user_msg
    new_state["final_reply"] = user_msg

    # 将异常兜底的原因简要记录到思考过程，便于前端展示
    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking_note = DEFAULT_THINKING_BASE
    if raw_error:
        thinking_note += DEFAULT_THINKING_ERROR_SUFFIX.format(raw_error=raw_error)
    parts = [p for p in [prev_thinking, thinking_note] if p]
    new_state["thinking"] = "\n\n".join(parts)

    # 记录到流水线追踪，方便排查
    new_state.setdefault("pipeline_trace", {})
    new_state["pipeline_trace"]["default_handler"] = {
        "note": "异常兜底子图已执行，已从 fallback 列表随机回复。",
        "raw_error": raw_error,
    }

    return new_state


def build_default_handler_graph() -> CompiledStateGraph:
    """
    构建异常兜底子图 StateGraph，当前仅包含一个核心节点。

    入参：
    无入参。

    返回值：
    CompiledStateGraph：编译后的异常兜底子图，可供总图作为节点调用。

    关键逻辑：
    单节点子图：entry -> _default_handler_node -> END；后续可在此扩展更精细的异常分级与告警逻辑。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("default_handler", _default_handler_node)
    builder.set_entry_point("default_handler")
    builder.add_edge("default_handler", END)
    return builder.compile()

