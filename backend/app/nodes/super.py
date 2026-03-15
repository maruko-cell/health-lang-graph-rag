"""
汇总（Super）总图模块，用于将各子图作为黑盒节点编排，并通过条件边从入口路由到对应子图，最后统一经过 Summary 汇总节点产出最终回复。

入参：
无入参，本模块提供 build_super_graph() 供应用层调用。

返回值：
通过 build_super_graph() 返回编译后的总图（CompiledStateGraph）。

关键逻辑：
- 总图将 nodes 下各子图（rag / multi_moda / diet / exercise / surround_amap_maps_mcp / default_handler / summary）加入总图；
- 入口通过 _router_super 判断：有可选择的则走对应子图，没有可选择的走 default_handler；
- 所有子图（包括 default_handler）执行完成后统一进入 summary 汇总子图，由其汇总各子图结果并写入 final_reply，再到 END。
"""

from typing import Callable

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

import json
import time
from app.state import GraphState
from app.nodes.query_rewrite import query_rewrite_node
from app.nodes.rag import build_rag_graph
from app.nodes.multi_moda import build_multi_moda_graph
from app.nodes.diet import build_diet_graph
from app.nodes.exercise import build_exercise_graph
from app.nodes.surround_amap_maps_mcp import build_surround_amap_maps_mcp_graph
from app.nodes.default_handler import build_default_handler_graph
from app.nodes.selfie import build_selfie_graph
from app.nodes.summary import build_summary_graph
from app.nodes.intent import recognize_route


def get_router_fn() -> Callable[[GraphState], str]:
    """
    返回总图使用的路由函数，供流式层复用以在不动 Super 图的前提下得到 route。

    入参：无入参。
    返回值：Callable[[GraphState], str]，即 _router_super。
    """
    return _router_super


def get_subgraph_builders() -> dict[str, Callable[[], CompiledStateGraph]]:
    """
    返回路由名到子图 builder 的映射，供 Super 与流式层共用单一事实源。

    入参：无入参。
    返回值：dict[str, Callable]，键为 _router_super 返回值（rag / multi_moda / ... / default）。
    """
    return {
        "rag": build_rag_graph,
        "multi_moda": build_multi_moda_graph,
        "diet": build_diet_graph,
        "exercise": build_exercise_graph,
        "surround_amap_maps_mcp": build_surround_amap_maps_mcp_graph,
        "selfie": build_selfie_graph,
        "default": build_default_handler_graph,
    }


def get_summary_builder() -> Callable[[], CompiledStateGraph]:
    """
    返回汇总子图 builder，供 Super 与流式层共用。

    入参：无入参。
    返回值：Callable[[], CompiledStateGraph]，即 build_summary_graph。
    """
    return build_summary_graph


def _router_super_node(state: GraphState) -> GraphState:
    """
    总图路由节点（占位），不修改状态，仅作为条件边起点；实际分支由 _router_super 决定。

    入参：
    state：GraphState，当前图状态，含 query 等。

    返回值：
    GraphState：原样返回，不修改状态。

    关键逻辑：
    用于 LangGraph 条件边起点，真正路由逻辑在 _router_super 中。
    """
    return state


def _router_super(state: GraphState) -> str:
    """
    根据用户输入与多模态上下文判断：有可选择的则走对应子图，没有可选择的走 default_handler。

    入参：
    state：GraphState，当前图状态，可读 query 与 image_path 等字段。

    返回值：
    str：路由标签 "rag" | "multi_moda" | "diet" | "exercise" | "surround_amap_maps_mcp" | "default"，需与 add_conditional_edges 的 mapping 一致。

    关键逻辑：
    - 若 state 中有 force_route（如前端传入 agent_type 为 selfie），则直接返回该路由；
    - 若当前状态中包含 image_path（说明本轮对话携带图片），则优先路由到 "multi_moda" 子图；
    - 否则调用 intent.recognize_route(query) 得到路由。
    """
    force = (state.get("force_route") or "").strip()
    if force and force in ("rag", "multi_moda", "diet", "exercise", "surround_amap_maps_mcp", "selfie", "default"):
        return force
    image_path = (state.get("image_path") or "").strip()
    q = (state.get("query") or "").strip()
    if image_path:
        route = "multi_moda"
    else:
        route = recognize_route(q)
    return route


def build_super_graph() -> CompiledStateGraph:
    """
    构建总图 StateGraph：将各子图加入总图，入口经条件边由 _router_super 选择子图，子图与 default_handler 执行完成后统一进入 summary 汇总再结束。

    入参：
    无入参。

    返回值：
    CompiledStateGraph：编译后的总图，可供路由层 invoke/ainvoke 调用。

    关键逻辑：
    - 构建 rag / multi_moda / diet / exercise / surround_amap_maps_mcp / default_handler / summary 七个子图并加入总图；
    - 入口为 _router_super 节点，经条件边：有可选择的走对应子图，无则走 default_handler；
    - 各业务子图与 default_handler 执行后统一进入 summary 子图，由其汇总结果并写入 final_reply，最后到 END。
    """
    builders = get_subgraph_builders()
    rag_graph = builders["rag"]()
    multi_moda_graph = builders["multi_moda"]()
    diet_graph = builders["diet"]()
    exercise_graph = builders["exercise"]()
    surround_amap_maps_mcp_graph = builders["surround_amap_maps_mcp"]()
    selfie_graph = builders["selfie"]()
    default_handler_graph = builders["default"]()
    summary_graph = get_summary_builder()()

    async def rag_subgraph_node(state: GraphState) -> GraphState:
        """
        RAG 子图包装节点，将当前状态转交给 RAG 子图异步执行。

        入参：
        state：GraphState，当前图状态。

        返回值：
        GraphState：RAG 子图执行后的最新状态。

        关键逻辑：
        通过子图的 ainvoke 方法异步执行，便于总图 astream 时边算边推。
        """
        return await rag_graph.ainvoke(state)

    async def multi_moda_subgraph_node(state: GraphState) -> GraphState:
        return await multi_moda_graph.ainvoke(state)

    async def diet_subgraph_node(state: GraphState) -> GraphState:
        return await diet_graph.ainvoke(state)

    async def exercise_subgraph_node(state: GraphState) -> GraphState:
        return await exercise_graph.ainvoke(state)

    async def surround_amap_maps_mcp_subgraph_node(state: GraphState) -> GraphState:
        return await surround_amap_maps_mcp_graph.ainvoke(state)

    async def selfie_subgraph_node(state: GraphState) -> GraphState:
        return await selfie_graph.ainvoke(state)

    async def default_handler_subgraph_node(state: GraphState) -> GraphState:
        return await default_handler_graph.ainvoke(state)

    async def summary_subgraph_node(state: GraphState) -> GraphState:
        return await summary_graph.ainvoke(state)

    builder: StateGraph[GraphState] = StateGraph(GraphState)

    builder.add_node("query_rewrite", query_rewrite_node)
    builder.add_node("_router_super_node", _router_super_node)
    builder.add_node("rag_subgraph", rag_subgraph_node)
    builder.add_node("multi_moda_subgraph", multi_moda_subgraph_node)
    builder.add_node("diet_subgraph", diet_subgraph_node)
    builder.add_node("exercise_subgraph", exercise_subgraph_node)
    builder.add_node("surround_amap_maps_mcp_subgraph", surround_amap_maps_mcp_subgraph_node)
    builder.add_node("selfie_subgraph", selfie_subgraph_node)
    builder.add_node("default_handler_subgraph", default_handler_subgraph_node)
    builder.add_node("summary_subgraph", summary_subgraph_node)

    # 入口 -> query 重写（带上下文）-> 路由 -> 各子图
    builder.set_entry_point("query_rewrite")
    builder.add_edge("query_rewrite", "_router_super_node")
    builder.add_conditional_edges(
        "_router_super_node",
        _router_super,
        {
            "rag": "rag_subgraph",
            "multi_moda": "multi_moda_subgraph",
            "diet": "diet_subgraph",
            "exercise": "exercise_subgraph",
            "surround_amap_maps_mcp": "surround_amap_maps_mcp_subgraph",
            "selfie": "selfie_subgraph",
            "default": "default_handler_subgraph",
        },
    )

    # 各业务子图与 default_handler 走完后均进入 summary；RAG 子图内已并行调用 KG，直接进入 summary
    for node in (
        "rag_subgraph",
        "multi_moda_subgraph",
        "diet_subgraph",
        "exercise_subgraph",
        "surround_amap_maps_mcp_subgraph",
        "selfie_subgraph",
        "default_handler_subgraph",
    ):
        builder.add_edge(node, "summary_subgraph")

    builder.add_edge("summary_subgraph", END)

    return builder.compile()
