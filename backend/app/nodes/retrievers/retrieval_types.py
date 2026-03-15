from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass
class RetrievedDoc:
    """
    表示一条通用检索结果的数据结构。

    入参（属性）：
    - doc_id：str，文档或分块的唯一标识；
    - text：str，文档片段文本内容；
    - score：float，本检索通道内部的原始相关度得分（如相似度、BM25 分数等）；
    - metadata：Dict[str, Any]，存放 file_id、source、chunk_index 等扩展元数据。

    返回值：
    - 无返回值，本类作为数据载体用于不同检索组件之间传递统一的结果格式。

    关键逻辑：
    - 提供统一的数据结构，便于向量检索、关键词检索与 RRF 融合组件之间共享检索结果。
    """

    doc_id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class Retriever(Protocol):
    """
    通用检索器协议，所有检索组件（向量、关键词、融合等）都应实现该接口。

    功能描述：
    - 约束检索组件对外暴露统一的 retrieve 方法，便于在 RRF 融合组件中以多态方式调用。

    入参说明：
    - query：str，用户查询文本或关键词；
    - top_k：int，希望返回的结果条数。

    返回值说明：
    - List[RetrievedDoc]：按当前检索通道内相关度从高到低排序的检索结果列表。

    关键逻辑备注：
    - 具体实现可以使用向量相似度、倒排索引/BM25 等任意策略，只需保证返回的列表是按“本通道视角”排序即可。
    """

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedDoc]:
        ...

