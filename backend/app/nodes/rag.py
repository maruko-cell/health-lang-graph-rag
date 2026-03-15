"""
RAG（检索增强生成）子图模块。

入参：
无入参，本模块提供子图构建函数 build_rag_graph() 供总图调用。

返回值：
通过 build_rag_graph() 返回编译后的子图（CompiledGraph）。

关键逻辑：
多节点子图：rag_start（检索中 + 向量/关键词）→ kg_entity → kg_cypher → kg_query → rag_fuse（融合中 + RRF + LLM）；
无 query 时 rag_start 后直接 END；thinking 随各节点追加，便于流式实时展示。
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from app.common.Prompt import RAG_HUMAN_TEMPLATE, RAG_SYSTEM_PROMPT
from app.common.prompt_utils import build_system_human_messages
from app.common.thinkings import (
    RAG_THINKING_FUSION,
    RAG_THINKING_KEYWORD_RESULT,
    RAG_THINKING_NO_DOCS,
    RAG_THINKING_NO_QUERY,
    RAG_THINKING_RETRIEVING,
    RAG_THINKING_RRF_RESULT,
    RAG_THINKING_SNIPPET_TEMPLATE,
    RAG_THINKING_VECTOR_RESULT,
)
from app.llm_agent.agent import create_llm_agent
from app.state import GraphState
from app.nodes.rag_state import RagState
from app.nodes.retrievers import kg_facts_to_docs, rrf_fuse
from app.nodes.retrievers.kg import kg_entity_node, kg_cypher_node, kg_query_node
from app.nodes.retrievers.rag_retriever import retrieve_vector_keyword

TOP_K = 5
INNER_TOP_K = 20
K_RRF = 60
# 检索结果预览：每条最多字符数、最多展示条数
_PREVIEW_MAX_CHARS = 100
_PREVIEW_MAX_ITEMS = 3


def _doc_list_preview(docs: list, max_items: int = _PREVIEW_MAX_ITEMS, max_chars: int = _PREVIEW_MAX_CHARS) -> str:
    """
    将检索结果列表格式化为简短预览文本，用于写入 thinking。

    入参：
    - docs：list，元素为具 .text 属性的对象（如 RetrievedDoc）。
    - max_items：int，最多展示几条。
    - max_chars：int，每条文本最多字符数。

    返回值：str，多行预览，无结果时返回「（无）」。
    """
    if not docs:
        return "（无）"
    lines = []
    for i, d in enumerate(docs[:max_items]):
        if d is None:
            continue
        text = (getattr(d, "text", None) or str(d)).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "…"
        if text:
            lines.append(f"  {i + 1}. {text}")
    if not lines:
        return "（无）"
    return "\n".join(lines)


def _call_llm_with_context(
    query: str,
    context_text: str,
    memory_context: str | None = None,
    chat_history_short: list | None = None,
) -> str:
    """
    使用参考内容与用户问题调用 LLM 生成回答；可选注入长期记忆与短期对话历史。

    入参：
    - query：str，用户问题。
    - context_text：str，检索得到的参考内容。
    - memory_context：str | None，长期记忆摘要，有则拼入参考内容前。
    - chat_history_short：list | None，最近 N 轮消息，有则做多轮上下文。

    返回值：str，模型回复文本。
    """
    if memory_context and (memory_context := memory_context.strip()):
        context_text = f"【已知用户信息】\n{memory_context}\n\n{context_text}"

    try:
        cfg = create_llm_agent()
        if chat_history_short and len(chat_history_short) > 0:
            messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]
            for item in chat_history_short:
                if isinstance(item, dict) and item.get("role") and item.get("content") is not None:
                    messages.append({"role": item["role"], "content": str(item["content"])})
            messages.append({"role": "user", "content": f"{context_text}\n\n【用户问题】\n{query}"})
        else:
            human = RAG_HUMAN_TEMPLATE.format(context_text=context_text, query=query)
            messages = build_system_human_messages(RAG_SYSTEM_PROMPT, human)
        return cfg.invoke_and_get_content(messages)
    except Exception as e:
        return f"【RAG】调用 LLM 失败：{e!s}"


def _rag_start_node(state: RagState) -> RagState:
    """
    RAG 子图节点 1：无 query 时写占位与 NO_QUERY thinking 并返回；有 query 时追加「检索中」并执行向量/关键词检索，写入 _vector_docs、_keyword_docs。

    入参：state，RagState，需包含 query。
    返回值：RagState，更新 thinking、_vector_docs、_keyword_docs 或 rag_answer（无 query 时）。
    """
    new_state: RagState = dict(state)
    new_state["rag_placeholder"] = "rag"

    query = (state.get("query") or "").strip()
    if not query:
        new_state["rag_answer"] = "【RAG】用户未提供查询问题。"
        prev_thinking = (new_state.get("thinking") or "").strip()
        thinking_parts = [p for p in [prev_thinking, RAG_THINKING_NO_QUERY] if p]
        new_state["thinking"] = "\n\n".join(thinking_parts)
        return new_state

    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking_parts = [p for p in [prev_thinking, RAG_THINKING_RETRIEVING] if p]
    new_state["thinking"] = "\n\n".join(thinking_parts)

    vector_docs, keyword_docs = retrieve_vector_keyword(query, inner_top_k=INNER_TOP_K)
    new_state["_vector_docs"] = vector_docs
    new_state["_keyword_docs"] = keyword_docs

    vector_preview = _doc_list_preview(vector_docs)
    vector_line = RAG_THINKING_VECTOR_RESULT.format(n=len(vector_docs), preview=vector_preview)
    prev_thinking = (new_state.get("thinking") or "").strip()
    new_state["thinking"] = "\n\n".join([p for p in [prev_thinking, vector_line] if p])

    keyword_preview = _doc_list_preview(keyword_docs)
    keyword_line = RAG_THINKING_KEYWORD_RESULT.format(n=len(keyword_docs), preview=keyword_preview)
    prev_thinking = (new_state.get("thinking") or "").strip()
    new_state["thinking"] = "\n\n".join([p for p in [prev_thinking, keyword_line] if p])

    return new_state


def _rag_fuse_node(state: RagState) -> RagState:
    """
    RAG 子图节点 5：追加「融合中」thinking，将 _vector_docs、_keyword_docs、kg_facts 做 RRF 融合后调 LLM 生成 rag_answer。

    入参：state，RagState，需包含 _vector_docs、_keyword_docs、kg_facts、query。
    返回值：RagState，更新 thinking、rag_answer。
    """
    new_state: RagState = dict(state)

    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking_parts = [p for p in [prev_thinking, RAG_THINKING_FUSION] if p]
    new_state["thinking"] = "\n\n".join(thinking_parts)

    vector_docs = new_state.get("_vector_docs") or []
    keyword_docs = new_state.get("_keyword_docs") or []
    kg_facts = (new_state.get("kg_facts") or "").strip()
    kg_docs = kg_facts_to_docs(kg_facts)
    fused = rrf_fuse(
        [vector_docs, keyword_docs, kg_docs],
        k=K_RRF,
        top_n=TOP_K,
    )

    if not fused:
        new_state["rag_answer"] = "【RAG】暂未检索到相关知识库内容，请先上传并等待知识库文件向量化完成。"
        prev_thinking = (new_state.get("thinking") or "").strip()
        thinking_parts = [p for p in [prev_thinking, RAG_THINKING_NO_DOCS] if p]
        new_state["thinking"] = "\n\n".join(thinking_parts)
        return new_state

    query = (new_state.get("query") or "").strip()
    context_text = "\n\n".join(d.text for d in fused)
    memory_context = (new_state.get("long_term_memory_context") or "").strip() or None
    chat_history_short = new_state.get("chat_history_short") or []
    answer = _call_llm_with_context(query, context_text, memory_context=memory_context, chat_history_short=chat_history_short)
    new_state["rag_answer"] = answer

    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking_snippet = answer.strip()[:120]
    rag_thinking = RAG_THINKING_SNIPPET_TEMPLATE.format(snippet=thinking_snippet)
    thinking_parts = [p for p in [prev_thinking, rag_thinking] if p]
    new_state["thinking"] = "\n\n".join(thinking_parts)
    return new_state


def _rag_route_after_start(state: RagState) -> str:
    """条件边：rag_start 之后有 query 走 kg_entity，无 query 走 end。入参：state。返回值：'kg_entity' | 'end'。"""
    query = (state.get("query") or "").strip()
    return "end" if not query else "kg_entity"


def build_rag_graph() -> CompiledStateGraph:
    """
    构建 RAG 子图 StateGraph：rag_start →（有 query）kg_entity → kg_cypher → kg_query → rag_fuse → END；无 query 时 rag_start → END。

    入参：无入参。
    返回值：CompiledStateGraph，可供总图或流式层调用。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("rag_start", _rag_start_node)
    builder.add_node("kg_entity", kg_entity_node)
    builder.add_node("kg_cypher", kg_cypher_node)
    builder.add_node("kg_query", kg_query_node)
    builder.add_node("rag_fuse", _rag_fuse_node)

    builder.set_entry_point("rag_start")
    builder.add_conditional_edges("rag_start", _rag_route_after_start, {"kg_entity": "kg_entity", "end": END})
    builder.add_edge("kg_entity", "kg_cypher")
    builder.add_edge("kg_cypher", "kg_query")
    builder.add_edge("kg_query", "rag_fuse")
    builder.add_edge("rag_fuse", END)
    return builder.compile()
