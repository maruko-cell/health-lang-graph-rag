"""
汇总（Summary）子图模块。

入参：
无入参，本模块提供子图构建函数 build_summary_graph() 供总图或其他子图调用。

返回值：
通过 build_summary_graph() 返回编译后的子图（CompiledStateGraph）。

关键逻辑：
读取各业务子图在 GraphState 上写入的结果字段，按一定顺序拼接为统一的自然语言回复，
同时写入 final_reply，便于前端直接展示最终答案。
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.common.thinkings import (
    SUMMARY_THINKING_NO_SOURCES,
    SUMMARY_THINKING_TEMPLATE,
)
from app.state import GraphState
from app.nodes.summary_state import SummaryState


def _summary_node(state: SummaryState) -> SummaryState:
    """
    汇总子图核心节点：收集各子图产出字段并生成最终回复。

    入参：
    state：SummaryState，当前图状态，包含各子图写入的结果字段。

    返回值：
    SummaryState：更新后的状态，写入 summary_combined_text 与 final_reply。

    关键逻辑：
    - 从状态中读取 rag / multi_moda / diet / exercise / surround_amap_maps_mcp / default_handler 等子图的结果；
    - 仅对非空字段进行汇总，并附上简要标签；
    - 将拼接后的文本写入 summary_combined_text 与 final_reply；
    - 在 pipeline_trace 中记录本次汇总使用到的字段，便于调试与追踪。
    """
    new_state: SummaryState = dict(state)

    parts: list[str] = []
    sources: list[str] = []

    rag_answer = (new_state.get("rag_answer") or "").strip()
    if rag_answer:
        parts.append(f"【知识检索回答】\n{rag_answer}")
        sources.append("rag_answer")

    multi_moda_insight = (new_state.get("multi_moda_insight") or "").strip()
    if multi_moda_insight:
        parts.append(f"【多模态理解】\n{multi_moda_insight}")
        sources.append("multi_moda_insight")

    diet_advice = (new_state.get("diet_advice") or "").strip()
    if diet_advice:
        parts.append(f"【饮食建议】\n{diet_advice}")
        sources.append("diet_advice")

    kg_facts = (new_state.get("kg_facts") or "").strip()
    if kg_facts:
        parts.append(f"【知识图谱事实】\n{kg_facts}")
        sources.append("kg_facts")

    exercise_advice = (new_state.get("exercise_advice") or "").strip()
    if exercise_advice:
        parts.append(f"【运动建议】\n{exercise_advice}")
        sources.append("exercise_advice")

    surround_result = (new_state.get("surround_amap_maps_mcp_result") or "").strip()
    if surround_result:
        parts.append(f"【周边位置与地图信息】\n{surround_result}")
        sources.append("surround_amap_maps_mcp_result")

    selfie_advice = (new_state.get("selfie_advice") or "").strip()
    if selfie_advice:
        parts.append(f"【自画像】\n{selfie_advice}")
        sources.append("selfie_advice")

    user_friendly_error = (new_state.get("user_friendly_error") or "").strip()
    if user_friendly_error:
        parts.append(f"【异常提示】\n{user_friendly_error}")
        sources.append("user_friendly_error")

    if parts:
        combined = "\n\n".join(parts)
    else:
        combined = "当前没有可供汇总的子图结果，请稍后重试或换一个健康相关的问题问我哦～"

    new_state["summary_combined_text"] = combined
    new_state["final_reply"] = combined

    # 在 thinking 中补充一段总览式思考描述
    prev_thinking = (new_state.get("thinking") or "").strip()
    if sources:
        joined_sources = "、".join(sources)
        summary_thinking = SUMMARY_THINKING_TEMPLATE.format(joined_sources=joined_sources)
    else:
        summary_thinking = SUMMARY_THINKING_NO_SOURCES
    thinking_parts = [p for p in [prev_thinking, summary_thinking] if p]
    new_state["thinking"] = "\n\n".join(thinking_parts)

    trace = new_state.get("pipeline_trace") or {}
    trace.setdefault("summary", {})
    trace["summary"]["used_fields"] = sources
    trace["summary"]["note"] = "summary 子图已执行，并基于上述字段生成最终回复。"
    new_state["pipeline_trace"] = trace  # type: ignore[assignment]

    return new_state


def build_summary_graph() -> CompiledStateGraph:
    """
    构建汇总子图 StateGraph，当前仅包含一个核心节点。

    入参：
    无入参。

    返回值：
    CompiledStateGraph：编译后的汇总子图，可供总图或其他子图作为节点调用。

    关键逻辑：
    单节点子图：entry -> _summary_node -> END；后续可扩展更复杂的多轮汇总或权重调整逻辑。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("summary", _summary_node)
    builder.set_entry_point("summary")
    builder.add_edge("summary", END)
    return builder.compile()

