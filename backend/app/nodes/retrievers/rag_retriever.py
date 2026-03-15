"""
RAG 检索编排模块：提供「带 KG 子图」的并行三路检索 + RRF 融合入口，供 RAG 子图调用。

功能描述：
- kg_facts_to_docs：将 KG 子图产出的 kg_facts 字符串转为 RetrievedDoc 列表；
- retrieve_for_rag：并行执行向量检索、关键词检索与 KG 子图 invoke，三路结果 RRF 融合后返回，
  便于 RAG 节点直接拼 context 调 LLM，无需在 RAG 内写并行与融合逻辑。

入参：见各函数入参说明。

返回值：见各函数返回值说明。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Tuple

from app.state import GraphState

from .retrieval_types import RetrievedDoc
from .keyword_retriever import KeywordRetriever
from .rrf_retriever import rrf_fuse
from .vector_retriever import VectorRetriever

# 模块内单例，供 retrieve_for_rag 使用
_VECTOR_RETRIEVER = VectorRetriever()
_KEYWORD_RETRIEVER = KeywordRetriever.from_chroma()

# 将 KG 子图产出的 kg_facts 字符串转为 RetrievedDoc 列表，供 RRF 与向量/关键词结果融合。
def kg_facts_to_docs(kg_facts: str) -> List[RetrievedDoc]:
    """
    将 KG 子图产出的 kg_facts 字符串转为 RetrievedDoc 列表，供 RRF 与向量/关键词结果融合。

    功能描述：
    - 按行解析 kg_facts（每行一条「事实：A -关系-> B」），过滤空行后逐条转为 RetrievedDoc；
    - 便于与向量、关键词两路检索结果一起参与 rrf_fuse。

    入参说明：
    - kg_facts：str，KG 子图写入状态的事实文本，多行用换行分隔。

    返回值说明：
    - List[RetrievedDoc]：与检索协议一致的事实文档列表；无内容时返回空列表。
    """
    if not (kg_facts or "").strip():
        return []
    docs: List[RetrievedDoc] = []
    for i, line in enumerate((kg_facts or "").strip().split("\n")):
        line = line.strip()
        if not line:
            continue
        doc_id = f"kg_{i}_{hash(line) % 10**8}"
        docs.append(
            RetrievedDoc(
                doc_id=doc_id,
                text=line,
                score=1.0,
                metadata={"source": "neo4j"},
            )
        )
    return docs

def retrieve_vector_keyword(
    query: str,
    *,
    inner_top_k: int = 20,
) -> Tuple[List[RetrievedDoc], List[RetrievedDoc]]:
    """
    仅执行向量检索与关键词检索（不调用 KG），供 RAG 多节点子图中 rag_start 节点使用。

    入参：query，str；inner_top_k，int，每路检索条数。
    返回值：Tuple[List[RetrievedDoc], List[RetrievedDoc]]，(vector_docs, keyword_docs)。
    """
    vector_docs = _VECTOR_RETRIEVER.retrieve(query, top_k=inner_top_k)
    keyword_docs = _KEYWORD_RETRIEVER.retrieve(query, top_k=inner_top_k)
    return (vector_docs, keyword_docs)


# 并行执行向量检索、关键词检索与 KG 子图，将三路结果 RRF 融合后返回，供 RAG 子图拼 context 调 LLM。
def retrieve_for_rag(
    query: str,
    state: GraphState,
    kg_graph_invoke: Callable[[GraphState], GraphState],
    *,
    top_k: int = 5,
    inner_top_k: int = 5,
    k_rrf: int = 60,
) -> Tuple[List[RetrievedDoc], GraphState]:
    """
    并行执行向量检索、关键词检索与 KG 子图，将三路结果 RRF 融合后返回，供 RAG 子图拼 context 调 LLM。

    功能描述：
    - 使用 ThreadPoolExecutor 并行执行：向量检索、关键词检索、kg_graph_invoke(state)；
    - 将 KG 返回状态中的 kg_facts 转为 RetrievedDoc 列表，与另两路一起做 rrf_fuse；
    - 返回融合后的文档列表与 KG 执行后的 state，便于 RAG 合并 thinking/kg_facts 并拼 context。

    入参说明：
    - query：str，用户查询文本；
    - state：GraphState，当前图状态，会传入 KG 子图；
    - kg_graph_invoke：Callable[[GraphState], GraphState]，KG 子图的 invoke 封装（如 lambda s: kg_graph.invoke(s)）；
    - top_k：int，RRF 融合后返回的文档条数；
    - inner_top_k：int，向量/关键词每路检索条数；
    - k_rrf：int，RRF 平滑参数 k。
 
    返回值说明：
    - Tuple[List[RetrievedDoc], GraphState]：融合后的文档列表与 KG 执行后的状态。
    """
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_vector = executor.submit(
            _VECTOR_RETRIEVER.retrieve,
            query,
            top_k=inner_top_k,
        )
        future_keyword = executor.submit(
            _KEYWORD_RETRIEVER.retrieve,
            query,
            top_k=inner_top_k,
        )
        future_kg = executor.submit(kg_graph_invoke, state)

        vector_docs: List[RetrievedDoc] = future_vector.result()
        keyword_docs: List[RetrievedDoc] = future_keyword.result()
        state_after_kg: GraphState = future_kg.result()

    kg_docs = kg_facts_to_docs(state_after_kg.get("kg_facts") or "")
    fused: List[RetrievedDoc] = rrf_fuse(
        [vector_docs, keyword_docs, kg_docs],
        k=k_rrf,
        top_n=top_k,
    )
    return (fused, state_after_kg)


__all__ = ["kg_facts_to_docs", "retrieve_for_rag", "retrieve_vector_keyword"]
