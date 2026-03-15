"""
图状态（GraphState）类型定义模块。

入参：
无入参，仅用于集中定义 LangGraph 图中节点共享的状态结构。

返回值：
无返回值，本模块只提供类型定义供其他节点与图装配代码引用。

关键逻辑：
统一管理健康助手任务图中各个子图读写的字段，保证主图与子图之间的数据结构一致。
"""

from typing import Any, Dict, TypedDict


class GraphState(TypedDict, total=False):
    """
    健康助手任务图的共享状态字典类型。

    入参：
    无入参，本类型仅作为 LangGraph 图中节点与子图之间的状态约定使用。

    返回值：
    无返回值，通过字段定义规范各节点可读写的数据结构。

    关键逻辑：
    - 作为整张图（主图 + 各子图）统一的状态容器；
    - 后续可逐步在此处补充分领域字段，例如用户档案、多模态缓存等。
    """

    # 基本对话输入
    query: str
    # 用户原始问句（query 重写节点写回带上下文的 query 后，原输入存于此，供展示/日志）
    query_original: str

    # 会话与用户标识（用于 memory 读写）
    user_id: str
    session_id: str

    # 短期记忆：最近 N 轮消息，供 LLM 多轮上下文
    chat_history_short: list
    # 长期记忆：已知用户信息摘要字符串，供回答「我是谁」等
    long_term_memory_context: str
    # 用户画像：与 exercise 等子图使用的 user_profile 一致
    user_profile: Dict[str, Any]

    # 多模态相关输入（例如图片路径），由上游在有图片的场景下写入
    image_path: str

    # 多模态相关输入：图片的 base64 Data URL，由后端在图片上传接口或多模态节点内部生成
    image_base64_url: str

    # 最终输出
    final_reply: str

    # 思考过程文本：由各子图 / 汇总节点在推理过程中逐步累积，可用于前端展示「思考中」内容
    thinking: str

    # 流水线追踪信息，用于记录各子图执行状态与调试数据
    pipeline_trace: Dict[str, Any]

    # 强制路由：由前端 agent_type 写入，路由时优先使用
    force_route: str

    # 预留若干占位字段，便于后续在子图中扩展
    rag_placeholder: str
    diet_placeholder: str
    exercise_placeholder: str
    multi_moda_placeholder: str
    selfie_placeholder: str

    # 子图产出字段（占位阶段由各子图写入占位文案，后续替换为真实内容）
    rag_answer: str
    # 知识图谱子图产出的事实文本，通常为若干条「事实：A -关系-> B」按行拼接
    kg_facts: str
    # KG 子图中间状态：实体列表（可序列化）、Cypher 与参数，供多节点子图传递
    _kg_entities: Any
    _kg_cypher: str
    _kg_params: Dict[str, Any]
    # RAG 子图中间状态：向量检索与关键词检索结果，供 rag_fuse 做 RRF 融合
    _vector_docs: Any
    _keyword_docs: Any
    multi_moda_insight: str
    diet_advice: str
    exercise_advice: str
    surround_amap_maps_mcp_result: str
    user_friendly_error: str
    # 自画像子图产出：生成图片 URL 与说明文案
    selfie_image_url: str
    selfie_advice: str
