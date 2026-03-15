"""
周边高德地图（Surround AMap Maps MCP）子图模块。

入参：
无入参，本模块提供子图构建函数 build_surround_amap_maps_mcp_graph() 供总图调用。

返回值：
通过 build_surround_amap_maps_mcp_graph() 返回编译后的子图（CompiledStateGraph）。

关键逻辑：
调用高德地图 MCP HTTP 服务，根据对话 query 进行周边地点检索，并将结果写入状态。
"""

import json

from app.common.mcp_http_client import call_mcp_http

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.common.thinkings import SURROUND_THINKING
from app.config import AMAP_MCP_TIMEOUT, AMAP_MCP_URL
from app.nodes.surround_amap_maps_mcp_state import SurroundAmapMapsMcpState
from app.state import GraphState

# 展示给用户的 POI 条数上限，避免回复过长。
AMAP_POIS_DISPLAY_LIMIT = 10

# 高德 POI 类型码到简短中文标签的映射（可选展示）。
AMAP_TYPECODE_LABELS: dict[str, str] = {
    "090100": "综合医院",
    "090101": "综合医院",
    "090102": "社区卫生服务中心",
    "090200": "专科医院",
    "090202": "口腔医院",
    "090207": "医院",
    "090209": "专科医院",
    "070000": "体检",
    "150904": "停车场",
}


def _format_amap_pois_response(response_text: str) -> str:
    """
    将高德 MCP 返回的原始 JSON-RPC 字符串解析并格式化为用户可读的文本。

    入参：
    response_text：str，call_mcp_http 返回的原始响应字符串（JSON-RPC 格式）。

    返回值：
    str：格式化后的文案。有 POI 时为「总括句 + 编号列表（名称、地址，可选类型）」；
        解析失败或无 POI 时为兜底提示文案。

    关键逻辑：
    - 先解析外层 JSON 取 result.content[0].text，再解析内层取 suggestion、pois；
    - 仅使用 pois 列表，逐条取 name、address，可选附加 typecode 对应中文类型；
    - 条数受 AMAP_POIS_DISPLAY_LIMIT 限制；任一步解析失败则返回兜底文案。
    """
    if not (response_text or response_text.strip()):
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    try:
        outer = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    result = outer.get("result")
    if not result or not isinstance(result, dict):
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    content = result.get("content")
    if not content or not isinstance(content, list) or len(content) == 0:
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    text_payload = content[0].get("text") if isinstance(content[0], dict) else None
    if not text_payload or not isinstance(text_payload, str):
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    try:
        inner = json.loads(text_payload)
    except (json.JSONDecodeError, TypeError):
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    pois = inner.get("pois")
    if not pois or not isinstance(pois, list):
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    parts: list[str] = []
    limit = min(len(pois), AMAP_POIS_DISPLAY_LIMIT)
    for i, item in enumerate(pois[:limit], start=1):
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip() or "未知"
        address = (item.get("address") or "").strip() or "地址暂无"
        typecode = (item.get("typecode") or "").strip()
        type_label = AMAP_TYPECODE_LABELS.get(typecode, "")
        if type_label:
            line = f"{i}. {name}（{type_label}） - {address}"
        else:
            line = f"{i}. {name} - {address}"
        parts.append(line)

    if not parts:
        return "暂未找到周边相关地点，请换个关键词或区域试试。"

    total = len(pois)
    summary = f"根据您的关键词，找到以下 {total} 个相关地点（展示前 {limit} 条）："
    return summary + "\n" + "\n".join(parts)


def _surround_amap_maps_mcp_node_handle(
    state: SurroundAmapMapsMcpState,
) -> SurroundAmapMapsMcpState:
    """
    周边高德地图子图内节点，调用高德地图 MCP 服务并将检索结果写入状态。

    入参：
    state：SurroundAmapMapsMcpState，当前图状态，可读 query 等字段。

    返回值：
    SurroundAmapMapsMcpState：更新后的状态，写入 surround_amap_maps_mcp_placeholder、surround_amap_maps_mcp_result 字段。

    关键逻辑：
    - 从全局状态中读取用户 query；
    - 调用环境变量 AMAP_MCP_URL 指定的高德 MCP HTTP 服务；
    - 将返回结果（或错误信息）写入子图状态，供后续节点或总图使用。
    """
    new_state: SurroundAmapMapsMcpState = dict(state)
    new_state["surround_amap_maps_mcp_placeholder"] = "surround_amap_maps_mcp"

    query = state.get("query") or ""

    try:
        # 按 MCP Streamable HTTP 规范封装 JSON-RPC 2.0 消息，使用 tools/call 调用高德 MCP 工具。
        # 当前节点没有经纬度入参，因此默认使用 maps_text_search（仅需 keywords）。
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "maps_text_search",
                "arguments": {
                    "keywords": query,
                },
            },
        }
        response_text = call_mcp_http(
            AMAP_MCP_URL,
            payload=payload,
            timeout=int(AMAP_MCP_TIMEOUT),
            method="POST",
        )
        new_state["surround_amap_maps_mcp_result"] = _format_amap_pois_response(
            response_text
        )
    except Exception as exc:
        new_state["surround_amap_maps_mcp_result"] = f"调用高德地图 MCP 失败：{exc}"

    # 在 thinking 字段中追加本子图的思考描述，便于前端展示整体推理过程
    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking_parts = [p for p in [prev_thinking, SURROUND_THINKING] if p]
    new_state["thinking"] = "\n\n".join(thinking_parts)

    return new_state


def build_surround_amap_maps_mcp_graph() -> CompiledStateGraph:
    """
    构建周边高德地图子图 StateGraph。

    入参：
    无入参。

    返回值：
    CompiledStateGraph：编译后的周边高德地图子图，可供总图作为节点调用。

    关键逻辑：
    单节点子图：entry -> _surround_amap_maps_mcp_node_handle -> END；
    后续可在此增加地图检索、路径规划等节点与条件边。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node(
        "surround_amap_maps_mcp",
        _surround_amap_maps_mcp_node_handle,
    )
    builder.set_entry_point("surround_amap_maps_mcp")
    builder.add_edge("surround_amap_maps_mcp", END)
    return builder.compile()
