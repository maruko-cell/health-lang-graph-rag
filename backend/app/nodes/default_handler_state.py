"""
异常兜底（DefaultHandler）子图状态定义模块。

在全局 GraphState 基础上，明确异常兜底子图会读写的字段，便于 IDE 提示与静态类型检查。
"""

from typing import TypedDict

from app.state import GraphState


class DefaultHandlerState(GraphState, total=False):
    """异常兜底子图在 GraphState 上关注和写入的字段。"""

    # 异常占位标记，标识默认异常处理子图已执行
    error_placeholder: str

    # 原始异常信息，由上游节点或调用方写入
    error_message: str

    # 面向用户的友好错误提示文案
    user_friendly_error: str

    # pipeline_trace 继承自 GraphState，本子图会写入 default_handler 的追踪信息
