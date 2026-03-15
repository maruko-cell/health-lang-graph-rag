"""
汇总（Summary）子图状态定义模块。

入参：
无入参，仅用于集中描述与汇总子图相关的状态字段。

返回值：
无返回值，提供 TypedDict 类型供汇总子图节点使用。

关键逻辑：
在全局 GraphState 基础上，明确汇总子图会读写的字段，便于 IDE 提示与静态类型检查。
"""

from typing import TypedDict

from app.state import GraphState


class SummaryState(GraphState, total=False):
    """
    汇总子图在 GraphState 上关注和写入的字段定义。

    入参：
    无入参，本类型仅作为节点函数的类型提示使用。

    返回值：
    无返回值，通过字段说明当前子图会用到哪些状态。

    关键逻辑：
    - 继承全局 GraphState，使其兼容整张任务图的状态；
    - 明确汇总子图会读取 / 写入的字段，便于团队协作与维护。
    """

    # 汇总后的整体文本（便于在调试时查看未加装饰的原始拼接内容）
    summary_combined_text: str

