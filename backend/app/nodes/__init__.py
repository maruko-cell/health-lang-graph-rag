"""
节点模块初始化，统一导出图状态与子图构建入口。

入参：
无入参。

返回值：
无返回值，仅用于提供 GraphState 类型及各子图 build_xxx_graph 的命名空间。

关键逻辑：
- GraphState 由 app.state 定义，此处仅做 re-export 便于历史代码从 app.nodes 导入；
- 各子图（rag / diet / exercise / multi_moda）与总图（super）的 build_xxx_graph 由对应模块提供。
"""

from app.state import GraphState

__all__ = ["GraphState"]
