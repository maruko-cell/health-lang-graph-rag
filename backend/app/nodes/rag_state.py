"""
RAG（检索增强生成）子图状态定义模块。

入参：
无入参，仅用于集中描述与 RAG 子图相关的状态字段。

返回值：
无返回值，提供 TypedDict 类型供 RAG 子图节点使用。

关键逻辑：
在全局 GraphState 基础上，明确 RAG 子图会读写的字段，便于 IDE 提示与静态类型检查。
"""

from typing import TypedDict

from app.state import GraphState


class RagState(GraphState, total=False):
    """
    RAG 子图在 GraphState 上关注和写入的字段定义。

    入参：
    无入参，本类型仅作为节点函数的类型提示使用。

    返回值：
    无返回值，通过字段说明当前子图会用到哪些状态。

    关键逻辑：
    - 继承全局 GraphState，使其兼容整张任务图的状态；
    - 明确 RAG 子图会读取 / 写入的字段，便于团队协作与维护。
    """

    # 子图占位标记字段，标识 RAG 子图已被执行
    rag_placeholder: str

    # RAG 子图给出的基础回答内容
    rag_answer: str

