from __future__ import annotations

from typing import Dict, List, Sequence

from app.retrievers.retrieval_types import RetrievedDoc, Retriever


def rrf_fuse(
    ranked_lists: Sequence[Sequence[RetrievedDoc]],
    *,
    k: int = 60,
    top_n: int = 10,
) -> List[RetrievedDoc]:
    """
    使用 Reciprocal Rank Fusion (RRF) 对多路检索结果进行融合。

    功能描述：
    - 将来自不同检索通道（向量、关键词等）的有序检索结果列表进行融合；
    - 仅依赖每个通道内部的“排名顺序”，不直接比较不同通道的原始得分；
    - 返回统一的 RetrievedDoc 列表，按 RRF 总得分从高到低排序。

    入参说明：
    - ranked_lists：Sequence[Sequence[RetrievedDoc]]，多个检索通道的有序结果列表，
      每个内部列表应已按各自通道相关度降序排序；
    - k：int，RRF 平滑参数，值越大不同名次间差距越小，常见取值为 10~60；
    - top_n：int，融合后希望返回的结果条数。

    返回值说明：
    - List[RetrievedDoc]：融合后按 RRF 得分排序的检索结果列表。

    关键逻辑备注：
    - 对于每个文档 d，其 RRF 得分为 sum_i 1 / (k + rank_i(d))；
    - 若某文档只在部分通道出现，则仅累加出现通道的贡献；
    - 为简化实现，遇到同一 doc_id 的多个 RetrievedDoc 时，优先保留首个版本作为代表。
    """
    if not ranked_lists:
        return []

    scores: Dict[str, float] = {}
    best_doc_by_id: Dict[str, RetrievedDoc] = {}

    for result_list in ranked_lists:
        for rank, doc in enumerate(result_list, start=1):
            if doc.doc_id not in best_doc_by_id:
                best_doc_by_id[doc.doc_id] = doc
            scores[doc.doc_id] = scores.get(doc.doc_id, 0.0) + 1.0 / (k + rank)

    if not scores:
        return []

    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[: max(top_n, 1)]
    fused: List[RetrievedDoc] = []
    for doc_id, _ in sorted_ids:
        base = best_doc_by_id.get(doc_id)
        if not base:
            continue
        fused.append(base)

    return fused


class RrfFusionRetriever:
    """
    RRF 融合检索组件，将多个具体检索器（向量、关键词等）组合为一个统一检索入口。

    功能描述：
    - 持有若干实现 Retriever 协议的检索器实例；
    - 调用每个子检索器的 retrieve 方法获取有序结果列表；
    - 使用 rrf_fuse 对多路结果做 RRF 融合排序；
    - 对外暴露与其他检索器相同的 retrieve 接口，实现统一多态调用。

    入参说明：
    - retrievers：List[Retriever]，需要参与融合的具体检索器列表；
    - k：int，RRF 平滑参数，传递给 rrf_fuse；
    - per_channel_top_k：int | None，每个通道内部检索的最大条数，默认按 top_k * 2 估算。

    返回值说明：
    - retrieve(query, top_k)：返回融合后的 List[RetrievedDoc]。

    关键逻辑备注：
    - RRF 只依赖各通道内部的结果顺序及是否包含某文档，不要求各通道分数处于同一数值尺度；
    - 若后续需要调节不同通道“话语权”，可在调用 rrf_fuse 前对每路结果做截断或复制加权。
    """

    def __init__(
        self,
        retrievers: List[Retriever],
        *,
        k: int = 60,
        per_channel_top_k: int | None = None,
    ) -> None:
        self._retrievers = list(retrievers)
        self._k = k
        self._per_channel_top_k = per_channel_top_k

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedDoc]:
        """
        对外暴露的统一检索接口，实现 Retriever 协议。

        入参：
        - query：str，用户查询文本；
        - top_k：int，希望最终返回的融合结果条数。

        返回值：
        - List[RetrievedDoc]：按 RRF 得分排序的融合检索结果。
        """
        if not self._retrievers:
            return []

        inner_top_k = self._per_channel_top_k or max(top_k * 2, 20)
        ranked_lists: List[List[RetrievedDoc]] = []
        for r in self._retrievers:
            ranked_lists.append(r.retrieve(query, top_k=inner_top_k))

        return rrf_fuse(ranked_lists, k=self._k, top_n=top_k)


__all__: list[str] = ["rrf_fuse", "RrfFusionRetriever", "RetrievedDoc", "Retriever"]

