from __future__ import annotations

from typing import List, Optional

import chromadb

from app.common.embeddings import _compress_embeddings, _get_embeddings
from app.config import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR
from app.retrievers.retrieval_types import RetrievedDoc, Retriever


class VectorRetriever:
    """
    向量检索组件，基于 Chroma 与已有 embedding 逻辑实现相似度检索。

    功能描述：
    - 使用与向量化入库相同的 embedding 模型，将 query 转为向量；
    - 在 Chroma collection 中基于余弦相似度（hnsw:space=cosine）检索最相近的文档片段；
    - 将检索结果封装为统一的 RetrievedDoc 列表返回。

    入参说明：
    - collection_name：str | None，Chroma 集合名，默认使用配置 CHROMA_COLLECTION_NAME；
    - persist_dir：str | None，Chroma 持久化目录，默认使用配置 CHROMA_PERSIST_DIR；
    - max_n_results：int，单次检索允许返回的最大结果条数上限，用于保护性能上界。

    返回值说明：
    - retrieve(query, top_k)：返回 List[RetrievedDoc]，按向量相似度从高到低排序。

    关键逻辑备注：
    - 通过调用 app.tasks.vectorize_and_store 中的 _get_embeddings 与 _compress_embeddings
      保证检索端与入库端使用完全一致的向量表示；
    - Chroma 返回的是距离（distance，越小越相似），本实现将其简单映射为 score=1/(1+distance)，
      仅用于展示和调试，RRF 融合阶段只依赖 rank 顺序。
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_dir: Optional[str] = None,
        *,
        max_n_results: int = 50,
    ) -> None:
        self._collection_name: str = collection_name or CHROMA_COLLECTION_NAME or "default_collection"
        self._persist_dir: str = persist_dir or CHROMA_PERSIST_DIR or "./chroma_data"
        self._max_n_results: int = max_n_results

        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedDoc]:
        """
        基于向量相似度的检索接口，实现 Retriever 协议。

        入参：
        - query：str，用户查询文本；
        - top_k：int，希望返回的结果条数。

        返回值：
        - List[RetrievedDoc]：按相似度由高到低排序的检索结果列表。
        """
        text = (query or "").strip()
        if not text:
            return []

        # 1. 计算查询向量（复用现有 embedding 实现）
        q_embeddings = _get_embeddings([text])
        if not q_embeddings:
            return []
        q_embeddings = _compress_embeddings(q_embeddings)
        if not q_embeddings:
            return []

        # 2. 在 Chroma 中做相似度检索
        n_results = min(max(top_k, 1), self._max_n_results)
        try:
            results = self._collection.query(
                query_embeddings=[q_embeddings[0]],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        retrieved: List[RetrievedDoc] = []
        for doc_id, doc_text, meta, dist in zip(ids, documents, metadatas, distances):
            try:
                distance_value = float(dist)
            except Exception:
                distance_value = 0.0
            # 将距离映射为简单得分，值越大代表越相近，仅用于参考
            score = 1.0 / (1.0 + max(distance_value, 0.0))
            retrieved.append(
                RetrievedDoc(
                    doc_id=str(doc_id),
                    text=str(doc_text),
                    score=score,
                    metadata=dict(meta or {}),
                )
            )

        return retrieved


__all__: list[str] = ["VectorRetriever", "RetrievedDoc", "Retriever"]

