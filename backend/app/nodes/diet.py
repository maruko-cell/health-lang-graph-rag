"""
饮食建议（Diet）子图模块。

入参：
无入参，本模块提供子图构建函数 build_diet_graph() 供总图调用。

返回值：
通过 build_diet_graph() 返回编译后的子图（CompiledGraph）。

关键逻辑：
当前为占位实现，子图内仅有一个节点，将子图名称写入状态；后续可结合用户健康数据与营养学规则生成个性化饮食建议。
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.common.thinkings import DIET_THINKING
from app.state import GraphState
from app.nodes.diet_state import DietState


def _diet_placeholder_node(state: DietState) -> DietState:
    """
    饮食子图内占位节点，仅将子图名称写入状态，便于总图识别与联调。

    入参：
    state：DietState，当前图状态，可读 query、rag_answer 等上游字段。

    返回值：
    DietState：更新后的状态，写入 diet_placeholder、diet_advice 占位内容。

    关键逻辑：
    占位阶段仅返回子图名称标识，不做真实饮食规划。
    """
    new_state: DietState = dict(state)
    new_state["diet_placeholder"] = "diet"
    new_state["diet_advice"] = "【子图占位】diet"

    # 占位阶段的思考过程描述，便于前端展示「思考中」的粗粒度信息
    prev_thinking = (new_state.get("thinking") or "").strip()
    parts = [p for p in [prev_thinking, DIET_THINKING] if p]
    new_state["thinking"] = "\n\n".join(parts)

    return new_state


def build_diet_graph() -> CompiledStateGraph:
    """
    构建饮食子图 StateGraph，当前仅包含一个占位节点。

    入参：
    无入参。

    返回值：
    CompiledStateGraph：编译后的饮食子图，可供总图作为节点调用。

    关键逻辑：
    单节点子图：entry -> _diet_placeholder_node -> END；后续可在此增加规则节点、计划节点与条件边。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("diet_placeholder", _diet_placeholder_node)
    builder.set_entry_point("diet_placeholder")
    builder.add_edge("diet_placeholder", END)
    return builder.compile()
