from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

import chromadb

from app.config import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR
from app.retrievers.retrieval_types import RetrievedDoc, Retriever


class KeywordRetriever:
    """
    关键词检索组件，基于简单倒排索引与词频打分实现关键字匹配检索。

    功能描述：
    - 将文档片段文本进行分词，构建 token -> 文档集合 的倒排索引；
    - 对查询做相同分词，根据命中的 token 在各文档上的出现情况计算分数；
    - 返回按关键词相关度由高到低排序的 RetrievedDoc 列表。

    入参说明：
    - docs：Sequence[RetrievedDoc]，用于构建索引的基础文档列表；
    - min_token_len：int，最小 token 长度，小于该长度的 token 将被忽略；
    - case_sensitive：bool，是否区分大小写，默认不区分。

    返回值说明：
    - retrieve(query, top_k)：返回 List[RetrievedDoc]，按关键词匹配得分排序。

    关键逻辑备注：
    - 该实现不依赖外部 BM25 库，使用简化的“命中 token 数量 + 词频”作为得分；
    - 对中文场景，可替换 _tokenize 实现接入 jieba 等分词器，以获得更好效果；
    - 为避免与向量检索强耦合，本组件只依赖传入的 docs 或 from_chroma 类方法构建索引。
    """

    def __init__(
        self,
        docs: Sequence[RetrievedDoc],
        *,
        min_token_len: int = 2,
        case_sensitive: bool = False,
    ) -> None:
        self._min_token_len = max(min_token_len, 1)
        self._case_sensitive = case_sensitive

        # 保存原始文档列表，便于根据 doc_id 回溯
        self._docs_by_id: Dict[str, RetrievedDoc] = {}
        for d in docs:
            self._docs_by_id[d.doc_id] = d

        # 构建简单倒排索引：token -> {doc_id: 词频}
        self._inverted_index: Dict[str, Dict[str, int]] = {}
        for d in docs:
            tokens = self._tokenize(d.text)
            for token in tokens:
                if len(token) < self._min_token_len:
                    continue
                bucket = self._inverted_index.setdefault(token, {})
                bucket[d.doc_id] = bucket.get(d.doc_id, 0) + 1

    @staticmethod
    def _normalize(text: str, case_sensitive: bool) -> str:
        """
        归一化文本：根据大小写设置决定是否统一转为小写。

        入参：
        - text：待处理文本；
        - case_sensitive：是否区分大小写。

        返回值：
        - str：归一化后的文本。
        """
        return text if case_sensitive else text.lower()

    def _tokenize(self, text: str) -> List[str]:
        """
        对文本进行基础分词。

        入参：
        - text：待分词文本。

        返回值：
        - List[str]：按正则规则拆分得到的 token 列表。

        关键逻辑：
        - 当前实现使用正则按非字母数字与非中文字符拆分，适用于中英文混合的粗粒度分词；
        - 后续可替换为更智能的中文分词器（如 jieba），以提升关键词检索效果。
        """
        normalized = self._normalize(text, self._case_sensitive)
        # 将中文字符和字母数字视为 token，其他符号作为分隔符
        tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", normalized)
        return tokens

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedDoc]:
        """
        基于已构建的倒排索引对查询进行关键词检索。

        入参：
        - query：用户输入的查询文本；
        - top_k：希望返回的结果条数。

        返回值：
        - List[RetrievedDoc]：按关键词匹配得分从高到低排序的检索结果。

        关键逻辑：
        - 对 query 分词，统计每个命中 token 在各文档中的词频；
        - 文档得分为命中 token 词频之和，并可附加“命中 token 种类数”提升多样性；
        - 最终按得分排序并截取前 top_k 条记录。
        """
        text = (query or "").strip()
        if not text:
            return []

        tokens = self._tokenize(text)
        if not tokens:
            return []

        doc_scores: Dict[str, Tuple[int, int]] = {}
        # (total_freq, unique_token_count)

        for token in tokens:
            if len(token) < self._min_token_len:
                continue
            posting = self._inverted_index.get(token)
            if not posting:
                continue
            for doc_id, freq in posting.items():
                total, uniq = doc_scores.get(doc_id, (0, 0))
                total += freq
                uniq += 1
                doc_scores[doc_id] = (total, uniq)

        # 根据 (total_freq, unique_token_count) 排序
        scored_docs: List[Tuple[str, float]] = []
        for doc_id, (total_freq, uniq_tokens) in doc_scores.items():
            score = float(total_freq) + 0.1 * float(uniq_tokens)
            scored_docs.append((doc_id, score))

        scored_docs.sort(key=lambda x: x[1], reverse=True)
        top_ids = [doc_id for doc_id, _ in scored_docs[: max(top_k, 1)]]

        results: List[RetrievedDoc] = []
        for doc_id in top_ids:
            base = self._docs_by_id.get(doc_id)
            if not base:
                continue
            # 使用关键词得分覆盖原有 score，便于区分不同通道
            _, uniq = doc_scores.get(doc_id, (0, 0))
            # 这里不重新计算 total_freq，仅将排序后的顺序映射回 RetrievedDoc，score 仅作参考
            results.append(
                RetrievedDoc(
                    doc_id=base.doc_id,
                    text=base.text,
                    score=float(uniq),
                    metadata=dict(base.metadata),
                )
            )

        return results

    @classmethod
    def from_chroma(
        cls,
        collection_name: Optional[str] = None,
        persist_dir: Optional[str] = None,
        *,
        max_docs: int = 5000,
    ) -> "KeywordRetriever":
        """
        从 Chroma collection 中加载文档构建 KeywordRetriever 索引。

        入参：
        - collection_name：str | None，Chroma 集合名，默认使用 CHROMA_COLLECTION_NAME；
        - persist_dir：str | None，Chroma 持久化目录，默认使用 CHROMA_PERSIST_DIR；
        - max_docs：int，最多加载的文档条数，用于防止一次性拉取过多数据。

        返回值：
        - KeywordRetriever：基于 Chroma 文档构建好的关键词检索实例。

        关键逻辑：
        - 使用 chromadb.PersistentClient 从指定 collection 读取前 max_docs 条 document；
        - 将其转换为 RetrievedDoc 列表并调用构造函数建立倒排索引；
        - 适合作为简易方案，在文档规模不特别大时直接重用 Chroma 存储。
        """
        coll_name = collection_name or CHROMA_COLLECTION_NAME or "default_collection"
        persist = persist_dir or CHROMA_PERSIST_DIR or "./chroma_data"

        client = chromadb.PersistentClient(path=persist)
        collection = client.get_or_create_collection(
            name=coll_name,
            metadata={"hnsw:space": "cosine"},
        )

        try:
            raw = collection.get(
                include=["documents", "metadatas"],
                limit=max_docs,
            )
        except Exception:
            return cls([])

        ids = raw.get("ids") or []
        documents = raw.get("documents") or []
        metadatas = raw.get("metadatas") or []

        docs: List[RetrievedDoc] = []
        for doc_id, text, meta in zip(ids, documents, metadatas):
            docs.append(
                RetrievedDoc(
                    doc_id=str(doc_id),
                    text=str(text),
                    score=0.0,
                    metadata=dict(meta or {}),
                )
            )

        return cls(docs)


__all__: list[str] = ["KeywordRetriever", "RetrievedDoc", "Retriever"]

