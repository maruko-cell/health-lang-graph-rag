"""
检索组件包，提供统一的向量检索、关键词检索与 RRF 融合检索实现。

入参：
- 无直接入参，本包通过导出类与工具函数供外部模块按需导入使用。

返回值：
- 无返回值，通过 __all__ 导出公共 API。

关键逻辑：
- retrieval_types：定义通用的 RetrievedDoc 数据结构与 Retriever 协议；
- vector_retriever：基于 Chroma 与向量相似度的检索实现；
- keyword_retriever：基于倒排索引/关键词匹配的检索实现；
- rrf_retriever：实现 RRF 融合逻辑与统一的融合检索器。
"""

import sys

# 将本包注册为 app.retrievers，使 from app.retrievers.retrieval_types / app.retrievers.neo4j 等导入可用
sys.modules["app.retrievers"] = sys.modules[__name__]
from . import retrieval_types
sys.modules["app.retrievers.retrieval_types"] = retrieval_types
from . import kg
sys.modules["app.retrievers.neo4j"] = kg

from .retrieval_types import RetrievedDoc, Retriever
from .keyword_retriever import KeywordRetriever
from .neo4j_retriever import Neo4jRetriever
from .rag_retriever import kg_facts_to_docs, retrieve_for_rag
from .rrf_retriever import RrfFusionRetriever, rrf_fuse
from .vector_retriever import VectorRetriever

__all__ = [
    "RetrievedDoc",
    "Retriever",
    "VectorRetriever",
    "KeywordRetriever",
    "Neo4jRetriever",
    "RrfFusionRetriever",
    "rrf_fuse",
    "kg_facts_to_docs",
    "retrieve_for_rag",
]

