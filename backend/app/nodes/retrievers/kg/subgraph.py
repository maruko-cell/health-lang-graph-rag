"""
知识图谱（KG）LangGraph 子图模块，与 Neo4j 检索能力同属 retrievers.kg 包。

功能描述：
- 从 GraphState 读取 query，经三节点（实体抽取 → 构建 Cypher → 执行查询）写入 kg_facts 与 thinking；
- 提供 build_kg_graph() 及三节点函数（kg_entity_node、kg_cypher_node、kg_query_node）供总图或 RAG 子图调用。

入参：无入参（模块级）。
返回值：通过 build_kg_graph() 返回编译后的子图；三节点函数可直接作为节点加入其他图。
"""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.common.thinkings import (
    KG_THINKING_BUILD_CYPHER,
    KG_THINKING_ENTITY_EXTRACTION,
    KG_THINKING_ENTITY_RESULT,
    KG_THINKING_EXEC_QUERY,
    KG_THINKING_NO_RESULT,
    KG_THINKING_CYPHER_RESULT,
    KG_THINKING_QUERY_RESULT,
    KG_THINKING_QUERY_RESULT_PREVIEW,
)
from app.config import BACKEND_ROOT
from app.state import GraphState

from .dict_entity_extractor import DictEntity, DictEntityExtractor
from .query_executor import run_query

# 延迟导入，避免与 app.nodes.retrievers 包加载时的循环依赖
_NEO4J_RETRIEVER = None
_DICT_EXTRACTOR = None


def _get_dict_extractor() -> DictEntityExtractor:
    """返回模块级 DictEntityExtractor 单例，字典路径与 Neo4jRetriever 一致。无入参。"""
    global _DICT_EXTRACTOR
    if _DICT_EXTRACTOR is None:
        dict_root = BACKEND_ROOT / "app" / "data" / "dict"
        _DICT_EXTRACTOR = DictEntityExtractor(dict_root=dict_root)
    return _DICT_EXTRACTOR


def _get_neo4j_retriever():
    """延迟加载 Neo4jRetriever 单例，避免循环导入。无入参，返回 Neo4jRetriever 实例。"""
    from app.nodes.retrievers import Neo4jRetriever
    return Neo4jRetriever()


def _ensure_neo4j_retriever():
    """返回模块级 Neo4jRetriever 单例，首次调用时初始化。无入参，返回 Neo4jRetriever 实例。"""
    global _NEO4J_RETRIEVER
    if _NEO4J_RETRIEVER is None:
        _NEO4J_RETRIEVER = _get_neo4j_retriever()
    return _NEO4J_RETRIEVER


def _record_to_fact_text(record: dict) -> str:
    """
    将单条图检索记录转为可读事实描述，供 LLM 上下文使用。

    入参：record，dict，包含 fromName、relType、toName 等键的查询记录。
    返回值：str，形如「事实：{fromName} -{relType}-> {toName}」的短句。
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


def kg_entity_node(state: GraphState) -> GraphState:
    """
    知识图谱子图节点 1：仅做实体抽取，追加实体抽取 thinking，将结果写入 _kg_entities。

    入参：state，GraphState，需包含 query。
    返回值：GraphState，更新 _kg_entities、thinking。
    """
    new_state: GraphState = dict(state)
    query = (state.get("query") or "").strip()
    if not query:
        return new_state

    prev_thinking = (new_state.get("thinking") or "").strip()
    parts = [p for p in [prev_thinking, KG_THINKING_ENTITY_EXTRACTION] if p]
    new_state["thinking"] = "\n\n".join(parts)

    extractor = _get_dict_extractor()
    entities = extractor.extract(query)
    new_state["_kg_entities"] = [{"text": e.text, "types": e.types} for e in entities]

    if entities:
        summary_parts = [f"{e.text}({','.join(e.types)})" for e in entities[:8]]
        summary = "、".join(summary_parts)
        if len(entities) > 8:
            summary += f" 等共 {len(entities)} 个"
        else:
            summary = f"共 {len(entities)} 个实体 — " + summary
    else:
        summary = "未识别到字典实体，将使用通用检索。"
    result_line = KG_THINKING_ENTITY_RESULT.format(summary=summary)
    prev_thinking = (new_state.get("thinking") or "").strip()
    new_state["thinking"] = "\n\n".join([p for p in [prev_thinking, result_line] if p])
    return new_state


def kg_cypher_node(state: GraphState) -> GraphState:
    """
    知识图谱子图节点 2：根据 _kg_entities 与 query 构建 Cypher，追加 thinking，写入 _kg_cypher、_kg_params。

    入参：state，GraphState，需包含 query、_kg_entities。
    返回值：GraphState，更新 _kg_cypher、_kg_params、thinking。
    """
    new_state: GraphState = dict(state)
    query = (state.get("query") or "").strip()
    raw_entities = state.get("_kg_entities") or []

    prev_thinking = (new_state.get("thinking") or "").strip()
    parts = [p for p in [prev_thinking, KG_THINKING_BUILD_CYPHER] if p]
    new_state["thinking"] = "\n\n".join(parts)

    entities: list[DictEntity] = [DictEntity(e["text"], e["types"]) for e in raw_entities if isinstance(e, dict) and "text" in e and "types" in e]
    retriever = _ensure_neo4j_retriever()
    cypher, params = retriever._build_cypher_with_fallback(
        query,
        entities,
        result_limit=10,
    )
    new_state["_kg_cypher"] = cypher or ""
    new_state["_kg_params"] = params or {}

    if cypher:
        cypher_preview = cypher.replace("\n", " ").strip()
        if len(cypher_preview) > 200:
            cypher_preview = cypher_preview[:200] + "…"
        result_line = KG_THINKING_CYPHER_RESULT.format(cypher_preview=cypher_preview)
    else:
        result_line = KG_THINKING_CYPHER_RESULT.format(cypher_preview="未能生成 Cypher，将跳过图检索。")
    prev_thinking = (new_state.get("thinking") or "").strip()
    new_state["thinking"] = "\n\n".join([p for p in [prev_thinking, result_line] if p])
    return new_state


def kg_query_node(state: GraphState) -> GraphState:
    """
    知识图谱子图节点 3：执行 _kg_cypher，将结果转为事实文本写入 kg_facts，并追加执行/无结果 thinking。

    入参：state，GraphState，需包含 _kg_cypher、_kg_params。
    返回值：GraphState，更新 kg_facts、thinking。
    """
    new_state: GraphState = dict(state)
    cypher = (state.get("_kg_cypher") or "").strip()
    params = state.get("_kg_params") or {}

    if not cypher:
        prev_thinking = (new_state.get("thinking") or "").strip()
        parts = [p for p in [prev_thinking, KG_THINKING_NO_RESULT] if p]
        new_state["thinking"] = "\n\n".join(parts)
        new_state["kg_facts"] = ""
        return new_state

    prev_thinking = (new_state.get("thinking") or "").strip()
    parts = [p for p in [prev_thinking, KG_THINKING_EXEC_QUERY] if p]
    new_state["thinking"] = "\n\n".join(parts)

    records = run_query(cypher, params)
    if not records:
        prev_thinking = (new_state.get("thinking") or "").strip()
        parts = [p for p in [prev_thinking, KG_THINKING_NO_RESULT] if p]
        new_state["thinking"] = "\n\n".join(parts)
        new_state["kg_facts"] = ""
        return new_state

    fact_lines = []
    for rec in records[:10]:
        line = _record_to_fact_text(rec)
        if line:
            fact_lines.append(line)
    new_state["kg_facts"] = "\n".join(fact_lines)

    n = len(records)
    if n <= 3:
        preview = "\n".join(fact_lines[:n])
        result_line = KG_THINKING_QUERY_RESULT_PREVIEW.format(n=n, preview=preview)
    else:
        result_line = KG_THINKING_QUERY_RESULT.format(n=n)
        preview_lines = fact_lines[:2]
        if preview_lines:
            result_line += "\n预览：" + "\n".join(preview_lines)
    prev_thinking = (new_state.get("thinking") or "").strip()
    new_state["thinking"] = "\n\n".join([p for p in [prev_thinking, result_line] if p])
    return new_state


def build_kg_graph() -> CompiledStateGraph:
    """
    构建知识图谱子图 StateGraph：entry → kg_entity → kg_cypher → kg_query → END。

    入参：无入参。
    返回值：CompiledStateGraph，可供总图或 RAG 子图作为子图调用。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("kg_entity", kg_entity_node)
    builder.add_node("kg_cypher", kg_cypher_node)
    builder.add_node("kg_query", kg_query_node)
    builder.set_entry_point("kg_entity")
    builder.add_edge("kg_entity", "kg_cypher")
    builder.add_edge("kg_cypher", "kg_query")
    builder.add_edge("kg_query", END)
    return builder.compile()
