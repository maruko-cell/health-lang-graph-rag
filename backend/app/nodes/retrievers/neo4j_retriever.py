"""
基于 Neo4j 医疗知识图谱的检索组件，实现 Retriever 协议并与 RRF 融合。

功能描述：
- 从用户 query 抽取检索词，在图内做实体匹配与 1～2 跳关系扩展，将结果转为事实文本；
- 封装为 RetrievedDoc 列表返回，供 RrfFusionRetriever 与向量/关键词检索融合。

入参说明：
- 无入参，Neo4j 连接与检索属性名从 app.config 读取（NEO4J_*、NEO4J_SEARCH_KEY）。

返回值说明：
- retrieve(query, top_k)：返回 List[RetrievedDoc]，按图内检索顺序排序；连接或查询失败时返回 []。
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from app.config import NEO4J_SEARCH_KEY
from app.retrievers.neo4j import get_driver, run_query
from app.retrievers.neo4j.dict_entity_extractor import DictEntity, DictEntityExtractor
from app.retrievers.neo4j.intention_and_templates import (
    IntentResult,
    QuestionIntent,
    SimpleIntentDetector,
    build_cypher_from_intent,
)
from app.retrievers.retrieval_types import RetrievedDoc, Retriever

# 将单条图检索记录转为可读事实描述，供 LLM 上下文使用。
def _record_to_fact_text(record: dict) -> str:
    """
    将单条图检索记录转为可读事实描述，供 LLM 上下文使用。

    入参：
    - record：dict，包含 fromName、relType、toName 等键的查询记录。

    返回值：
    - str：形如「事实：{fromName} -{relType}-> {toName}」的短句。
    """
    from_name = record.get("fromName") or record.get("from_name") or ""
    rel_type = record.get("relType") or record.get("rel_type") or ""
    to_name = record.get("toName") or record.get("to_name") or ""
    from_name = str(from_name).strip()
    rel_type = str(rel_type).strip()
    to_name = str(to_name).strip()
    if not from_name and not to_name:
        return ""
    return f"事实：{from_name} -{rel_type}-> {to_name}"

# 基于 Neo4j 医疗知识图谱的检索器，实现 Retriever 协议。
class Neo4jRetriever:
    """
    基于 Neo4j 医疗知识图谱的检索器，实现 Retriever 协议。

    功能描述：
    - 调用字典实体抽取与意图模板构建 Cypher，query_executor 执行；
    - 将图检索结果转为事实短句并封装为 RetrievedDoc，供 RRF 与向量/关键词融合。

    入参说明：
    - search_key：str | None，节点上用于匹配的属性名，默认使用配置 NEO4J_SEARCH_KEY（如 名称）；
    - max_entities：int，参与关系扩展的实体数量上限；
    - max_hops：int，关系扩展跳数（1 或 2）；
    - max_results：int，图检索返回的事实条数上限。
    """

    def __init__(
        self,
        search_key: Optional[str] = None,
        *,
        max_entities: int = 5,
        max_hops: int = 1,
        max_results: int = 30,
    ) -> None:
        self._search_key: str = search_key or NEO4J_SEARCH_KEY or "名称"
        self._max_entities = max_entities
        self._max_hops = min(max(1, max_hops), 2)
        self._max_results = max_results
        base_dir = Path(__file__).resolve().parent.parent / "data" / "dict"
        self._dict_extractor = DictEntityExtractor(dict_root=base_dir)
        self._intent_detector = SimpleIntentDetector()

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedDoc]:
        """
        基于用户问题在图内做实体匹配与关系扩展，返回事实形式的 RetrievedDoc 列表。

        入参：
        - query：str，用户查询文本；
        - top_k：int，希望返回的检索结果条数（本实现取 min(top_k, max_results)）。

        返回值：
        - List[RetrievedDoc]：事实文本列表，每条对应一条图检索结果；无结果或异常时返回 []。
        """
        if not get_driver():
            return []
        text = (query or "").strip()
        if not text:
            return []

        entities = self._dict_extractor.extract(text)
        cypher, params = self._build_cypher_with_fallback(
            text,
            entities,
            result_limit=min(self._max_results, max(top_k, 1)),
        )
        if not cypher:
            return []

        records = run_query(cypher, params)
        if not records:
            return []

        retrieved: List[RetrievedDoc] = []
        for i, rec in enumerate(records):
            fact_text = _record_to_fact_text(rec)
            if not fact_text:
                continue
            doc_id = f"neo4j_{i}_{hash(fact_text) % 10**8}"
            retrieved.append(
                RetrievedDoc(
                    doc_id=doc_id,
                    text=fact_text,
                    score=1.0,
                    metadata={"source": "neo4j"},
                )
            )
        return retrieved

    def _build_cypher_with_fallback(
        self,
        question: str,
        entities: List[DictEntity],
        *,
        result_limit: int,
    ) -> Tuple[str, dict]:
        """
        基于意图模板构建 Cypher；无匹配模板时直接返回空，不生成通用检索语句。

        功能描述：
        - 使用字典实体抽取结果与意图识别器构建模板化 Cypher；
        - 若无法识别意图或无法生成模板 Cypher，则返回 ("", {})，KG 子图将得到 0 条结果。

        入参说明：
        - question：str，原始用户问题；
        - entities：List[DictEntity]，字典实体抽取结果；
        - result_limit：int，最终返回结果条数上限。

        返回值说明：
        - Tuple[str, dict]：Cypher 语句与参数字典，若均为空则表示无法构建查询。
        """
        intent_result: IntentResult = self._intent_detector.detect(question, entities)
        for intent in intent_result.intents:
            cypher, params = build_cypher_from_intent(
                intent,
                intent_result.entities,
                question=question,
                search_key=self._search_key,
                max_results=result_limit,
            )
            if cypher:
                return cypher, params
        return "", {}


__all__ = ["Neo4jRetriever"]
