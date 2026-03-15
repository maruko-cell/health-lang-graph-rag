"""
多模态（Multi-Moda）子图模块。

入参：
无入参，本模块提供子图构建函数 build_multi_moda_graph() 供总图调用。

返回值：
通过 build_multi_moda_graph() 返回编译后的子图（CompiledGraph）。

关键逻辑：
当前实现包含一个多模态节点：读取图片 base64 Data URL（Data URL）与补充说明，调用智谱大模型进行结构化病理解读，
并将结果写入 multi_moda_insight 字段；后续可扩展音频、多图对比、结构化 JSON 输出等能力。
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.common.Prompt import MULTI_MODA_HUMAN_TEMPLATE, MULTI_MODA_SYSTEM_PROMPT
from app.common.thinkings import (
    MULTI_MODA_THINKING_BAD_URL,
    MULTI_MODA_THINKING_ERROR,
    MULTI_MODA_THINKING_NO_IMAGE,
    MULTI_MODA_THINKING_SNIPPET_TEMPLATE,
)
from app.state import GraphState
from app.nodes.multi_moda_state import MultiModaState
from app.llm_agent.agent import create_llm_agent


def _multi_moda_placeholder_node(state: MultiModaState) -> MultiModaState:
    """
    多模态占位节点：调用多模态大模型对上传的病理图片及说明进行解读，并将结果写入状态。

    入参：
    state: MultiModaState，多模态子图当前状态，包含图片 Data URL 与用户补充说明等信息。

    返回值：
    MultiModaState：更新后的状态，写入 multi_moda_insight 字段，包含多模态病理解读结果或错误信息。
    """
    new_state: MultiModaState = dict(state)
    new_state["multi_moda_placeholder"] = "multi_moda"

    image_base64_url = state.get("image_base64_url") or ""
    user_note = (state.get("query") or "").strip()

    # 校验：支持 Data URL（data:<mime>;base64,...）或可访问的 http(s) 图片 URL（如 OSS 地址）
    if not image_base64_url:
        new_state["multi_moda_insight"] = "【多模态】未提供图片 URL 或 Data URL，无法进行病理解读。"
        prev_thinking = (new_state.get("thinking") or "").strip()
        parts = [p for p in [prev_thinking, MULTI_MODA_THINKING_NO_IMAGE] if p]
        new_state["thinking"] = "\n\n".join(parts)
        return new_state
    is_data_url = image_base64_url.startswith("data:") and ";base64," in image_base64_url
    is_http_url = image_base64_url.startswith("http://") or image_base64_url.startswith("https://")
    if not is_data_url and not is_http_url:
        new_state["multi_moda_insight"] = "【多模态】图片格式错误，期望为 data:<mime>;base64,<...> 或 http(s) 可访问 URL。"
        prev_thinking = (new_state.get("thinking") or "").strip()
        parts = [p for p in [prev_thinking, MULTI_MODA_THINKING_BAD_URL] if p]
        new_state["thinking"] = "\n\n".join(parts)
        return new_state

    try:
        cfg = create_llm_agent(default_llm="zhipu")

        human_content = [
            {
                "type": "text",
                "text": MULTI_MODA_HUMAN_TEMPLATE.format(user_note=user_note),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_base64_url,
                },
            },
        ]

        messages: list[dict] = [
            {"role": "system", "content": MULTI_MODA_SYSTEM_PROMPT},
            {"role": "user", "content": human_content},
        ]

        content = cfg.invoke_and_get_content(messages)
        if not content:
            new_state["multi_moda_insight"] = "【多模态】模型返回内容为空，请稍后重试或更换图片。"
        else:
            new_state["multi_moda_insight"] = content

        # 将多模态病理解读的关键信息同步写入 thinking
        prev_thinking = (new_state.get("thinking") or "").strip()
        snippet = content[:120]
        mm_thinking = MULTI_MODA_THINKING_SNIPPET_TEMPLATE.format(snippet=snippet)
        parts = [p for p in [prev_thinking, mm_thinking] if p]
        new_state["thinking"] = "\n\n".join(parts)
    except Exception as e:
        new_state["multi_moda_insight"] = f"【多模态】调用模型失败：{e!s}"
        prev_thinking = (new_state.get("thinking") or "").strip()
        parts = [p for p in [prev_thinking, MULTI_MODA_THINKING_ERROR] if p]
        new_state["thinking"] = "\n\n".join(parts)

    return new_state


def build_multi_moda_graph() -> CompiledStateGraph:
    """
    构建多模态子图 StateGraph，当前包含一个多模态解读节点。

    入参：
    无入参。

    返回值：
    CompiledStateGraph：编译后的多模态子图，可供总图作为节点调用。

    关键逻辑：
    单节点子图：entry -> _multi_moda_placeholder_node -> END；后续可在此增加图像/语音解析节点与条件边。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("multi_moda_placeholder", _multi_moda_placeholder_node)
    builder.set_entry_point("multi_moda_placeholder")
    builder.add_edge("multi_moda_placeholder", END)
    return builder.compile()
