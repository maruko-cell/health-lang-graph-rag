"""
周边高德地图（Surround AMap Maps MCP）子图状态定义模块。

入参：
无入参，仅用于集中描述与周边高德地图子图相关的状态字段。

返回值：
无返回值，提供 TypedDict 类型供周边高德地图子图节点使用。

关键逻辑：
在全局 GraphState 基础上，明确周边高德地图子图会读写的字段，便于 IDE 提示与静态类型检查。
"""

from typing import TypedDict

from app.state import GraphState


class SurroundAmapMapsMcpState(GraphState, total=False):
    """
    周边高德地图（Surround AMap Maps MCP）子图在 GraphState 上关注和写入的字段定义。

    入参：
    无入参，本类型仅作为节点函数的类型提示使用。

    返回值：
    无返回值，通过字段说明当前子图会用到哪些状态。

    关键逻辑：
    - 继承全局 GraphState，使其兼容整张任务图的状态；
    - 明确周边高德地图子图会读取 / 写入的字段，便于团队协作与维护。
    """

    # 子图占位标记字段，标识周边高德地图子图已被执行
    surround_amap_maps_mcp_placeholder: str

    # 周边高德地图查询结果描述（占位或真实检索文案）
    surround_amap_maps_mcp_result: str

    # 周边检索关键词（可由上游节点写入；未提供时会回退使用 query）
    surround_amap_maps_keywords: str

    # 周边检索中心点经纬度，格式 "lng,lat"
    surround_amap_maps_location: str

    # 周边检索半径（米），可选
    surround_amap_maps_radius: str

    # MCP 原始响应文本，用于调试
    surround_amap_maps_mcp_raw_response: str

    # MCP 调用错误信息（如有）
    surround_amap_maps_mcp_error: str

