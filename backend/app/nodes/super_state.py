"""
汇总（Super）总图状态定义模块。

入参：
无入参，仅用于集中描述总图在 GraphState 上关注的关键字段。

返回值：
无返回值，提供 TypedDict 类型供 super 总图内部节点与路由函数使用。

关键逻辑：
在全局 GraphState 基础上，突出总图关心的最终回复与流水线追踪字段，便于 IDE 提示与静态类型检查。
"""

from typing import TypedDict

from app.state import GraphState


class SuperState(GraphState, total=False):
    """
    总图在 GraphState 上关注和写入的字段定义。

    入参：
    无入参，本类型仅作为总图内部节点与路由函数的类型提示使用。

    返回值：
    无返回值，通过字段说明总图会用到哪些状态。

    关键逻辑：
    - 继承全局 GraphState，使其兼容整张任务图的状态；
    - 明确总图会读取 / 写入的字段，便于团队协作与维护。
    """

    # 总图拼接后的最终自然语言回复
    final_reply: str

