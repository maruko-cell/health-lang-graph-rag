"""
query 重写子图：根据短期对话历史将当前用户问句补全为带上下文的 query，供主图后续各子图统一使用。

功能描述：
- 作为主图第一个节点执行，读 state["query"] 与 state["chat_history_short"]；
- 有历史时取最近 N 轮（N 可配置）格式化为 history_text，调用本地 LLM 做摘要，得到 summary 后与当前句拼接为 contextual_query，写回 state["query"]；
- 摘要失败时回退到实体补全或原 query；
- 原始用户输入写入 state["query_original"]，便于展示或日志使用。
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from app.config import (
    BACKEND_ROOT,
    QUERY_REWRITE_SUMMARY_MAX_INPUT_LEN,
    QUERY_REWRITE_SUMMARY_MAX_LEN,
    QUERY_REWRITE_SUMMARY_MAX_TURNS,
)
from app.state import GraphState

from app.common.Prompt import (
    QUERY_REWRITE_SUMMARY_HUMAN_TEMPLATE,
    QUERY_REWRITE_SUMMARY_SYSTEM,
)
from app.common.prompt_utils import build_system_human_messages
from app.llm_agent.agent import create_llm_agent
from app.nodes.retrievers.kg.dict_entity_extractor import DictEntityExtractor

# 模块级抽取器单例，与 KG 子图使用同一字典路径（摘要失败时实体回退用）
_DICT_EXTRACTOR: DictEntityExtractor | None = None

# 带上下文 query 最大长度，避免过长
QUERY_REWRITE_MAX_LEN = 200


def _get_extractor() -> DictEntityExtractor:
    """
    返回用于从历史中抽取实体的 DictEntityExtractor 单例，与 KG 字典路径一致。
    摘要失败时用于实体回退。

    功能描述：延迟初始化，避免模块加载时依赖未就绪。
    入参说明：无入参。
    返回值说明：DictEntityExtractor 实例。
    """
    global _DICT_EXTRACTOR
    if _DICT_EXTRACTOR is None:
        dict_root = BACKEND_ROOT / "app" / "data" / "dict"
        _DICT_EXTRACTOR = DictEntityExtractor(dict_root=dict_root)
    return _DICT_EXTRACTOR


def _get_last_turn_text(chat_history_short: list) -> str:
    """
    从短期对话历史中取最近一轮的文本并拼接为一段字符串，供实体抽取使用。

    功能描述：取最后 2 条消息（或最后 1 条），将其 content 拼成一段；若无历史则返回空串。
    入参说明：
    - chat_history_short：list，元素为 {"role":"user"|"assistant","content":"..."} 等。
    返回值说明：str，最近一轮的拼接文本。
    """
    if not chat_history_short or not isinstance(chat_history_short, list):
        return ""
    last_items = chat_history_short[-2:] if len(chat_history_short) >= 2 else chat_history_short[-1:]
    parts: List[str] = []
    for item in last_items:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if content is not None and str(content).strip():
            parts.append(str(content).strip())
    return " ".join(parts) if parts else ""


def _get_last_n_turns_text(chat_history_short: list, max_turns: int) -> str:
    """
    取最近 N 轮对话并格式化为「用户：…」「助手：…」多行文本，供摘要 LLM 使用；
    可选按 QUERY_REWRITE_SUMMARY_MAX_INPUT_LEN 从尾部截断。

    功能描述：从 chat_history_short 取最后 2*max_turns 条，按 role 转为「用户：content」或「助手：content」，换行拼接；超长则保留尾部截断。
    入参说明：
    - chat_history_short：list，短期记忆，元素为 {"role":"user"|"assistant","content":"..."}。
    - max_turns：int，参与摘要的轮数（每轮约 1 user + 1 assistant）。
    返回值说明：str，格式化后的历史文本；无有效内容则返回 ""。
    """
    if not chat_history_short or not isinstance(chat_history_short, list) or max_turns <= 0:
        return ""
    n_items = min(2 * max_turns, len(chat_history_short))
    last_items = chat_history_short[-n_items:]
    lines: List[str] = []
    for item in last_items:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if content is None:
            continue
        text = str(content).strip()
        if not text:
            continue
        if role == "user":
            lines.append(f"用户：{text}")
        else:
            lines.append(f"助手：{text}")
    if not lines:
        return ""
    raw = "\n".join(lines)
    if len(raw) > QUERY_REWRITE_SUMMARY_MAX_INPUT_LEN:
        raw = raw[-QUERY_REWRITE_SUMMARY_MAX_INPUT_LEN:].strip()
        
    return raw


def _summarize_turns(history_text: str) -> str:
    """
    调用本地 LLM 对最近几轮对话文本做摘要，返回 1～2 句概括；失败或空则返回 ""。

    功能描述：使用 QUERY_REWRITE_SUMMARY_SYSTEM 与 QUERY_REWRITE_SUMMARY_HUMAN_TEMPLATE 组 messages，调用 create_llm_agent().invoke_and_get_content；对返回值 strip 并按 QUERY_REWRITE_SUMMARY_MAX_LEN 截断；异常或空结果返回 ""。
    入参说明：
    - history_text：str，由 _get_last_n_turns_text 得到的格式化历史文本。
    返回值说明：str，摘要文本；失败或空则 ""。
    """
    if not (history_text or "").strip():
        return ""
    try:
        human = QUERY_REWRITE_SUMMARY_HUMAN_TEMPLATE.format(history_block=history_text.strip())
        messages = build_system_human_messages(QUERY_REWRITE_SUMMARY_SYSTEM, human)
        cfg = create_llm_agent()
        content = cfg.invoke_and_get_content(messages, default="")
        content = (content or "").strip()
        if not content:
            return ""
        if len(content) > QUERY_REWRITE_SUMMARY_MAX_LEN:
            content = content[:QUERY_REWRITE_SUMMARY_MAX_LEN]
        return content
    except Exception:
        return ""


def _build_contextual_query_with_summary(
    current_message: str,
    chat_history_short: list,
    max_turns: int,
) -> str:
    """
    用「摘要 + 当前句」生成带上下文的 query；摘要失败时回退到实体补全或原句。

    功能描述：取最近 max_turns 轮格式化为 history_text，调用 _summarize_turns 得 summary；非空则 summary + " " + current_message 并截断；空则回退到 _build_contextual_query（实体补全），再不行返回 current_message。
    入参说明：
    - current_message：str，本轮用户输入；
    - chat_history_short：list，短期对话历史；
    - max_turns：int，参与摘要的轮数。
    返回值说明：str，带上下文的 query 或原问句。
    """
    current_message = (current_message or "").strip()
    if not current_message:
        return current_message

    history_text = _get_last_n_turns_text(chat_history_short, max_turns)
    if not history_text:
        return current_message

    summary = _summarize_turns(history_text)
    if summary:
        # 调试：打印重新生成的摘要
        print("[query_rewrite] summary:", summary)
        contextual = f"{summary} {current_message}".strip()
        if len(contextual) > QUERY_REWRITE_MAX_LEN:
            contextual = contextual[:QUERY_REWRITE_MAX_LEN]
        return contextual

    # 摘要失败：回退到实体补全
    extractor = _get_extractor()
    return _build_contextual_query(current_message, chat_history_short, extractor)


def _build_contextual_query(
    current_message: str,
    chat_history_short: list,
    extractor: DictEntityExtractor,
) -> str:
    """
    根据当前问句与对话历史生成带上下文的 query；当前句已含疾病/症状实体则不补。
    用于摘要失败时的实体回退。

    功能描述：
    - 若当前句已包含疾病或症状实体，直接返回当前句；
    - 否则从最近一轮历史中抽取疾病/症状实体，将第一个实体拼到当前句前；
    - 无历史或无相关实体时返回原 current_message。

    入参说明：
    - current_message：str，本轮用户输入；
    - chat_history_short：list，短期对话历史；
    - extractor：DictEntityExtractor，字典实体抽取器。

    返回值说明：str，带上下文的 query 或原问句。
    """
    current_message = (current_message or "").strip()
    if not current_message:
        return current_message

    current_entities = extractor.extract(current_message)
    has_disease_or_symptom = any(
        "疾病" in t or "症状" in t for e in current_entities for t in e.types
    )
    if has_disease_or_symptom:
        return current_message

    last_turn_text = _get_last_turn_text(chat_history_short)
    if not last_turn_text:
        return current_message

    history_entities = extractor.extract(last_turn_text)
    context_entity = None
    for e in history_entities:
        if "疾病" in e.types or "症状" in e.types:
            context_entity = e.text
            break
    if not context_entity:
        return current_message

    contextual = f"{context_entity} {current_message}".strip()
    if len(contextual) > QUERY_REWRITE_MAX_LEN:
        contextual = contextual[:QUERY_REWRITE_MAX_LEN]
    return contextual


def query_rewrite_node(state: GraphState) -> GraphState:
    """
    主图首节点：从 state 读 query、chat_history_short；原句写入 query_original；
    有历史时用本地 LLM 摘要最近 N 轮后与当前句拼接写回 state["query"]，失败则实体回退或保持原 query。

    功能描述：
    - 读取 state["query"]、state["chat_history_short"]；
    - 若无历史则不重写，query 保持原样；
    - 有历史则取最近 N 轮（N 可配置）格式化为 history_text，调用 LLM 摘要得到 summary，contextual_query = summary + " " + current_message 再按 QUERY_REWRITE_MAX_LEN 截断；摘要失败则用实体回退；
    - 将结果写回 state["query"]，原 query 写入 state["query_original"]，pipeline_trace 写入 strategy 等便于排查。

    入参说明：
    - state：GraphState，需包含 query，可选 chat_history_short。

    返回值说明：GraphState，更新 query、query_original、pipeline_trace。
    """
    new_state: GraphState = dict(state)
    original_query = (state.get("query") or "").strip()
    new_state["query_original"] = original_query

    if not original_query:
        return new_state

    history = state.get("chat_history_short")
    if not history:
        new_state["query"] = original_query
        trace = dict(new_state.get("pipeline_trace") or {})
        trace["query_rewrite"] = {
            "query_original": original_query,
            "query_rewritten": original_query,
            "strategy": "no_history",
        }
        new_state["pipeline_trace"] = trace
        return new_state

    max_turns = QUERY_REWRITE_SUMMARY_MAX_TURNS
    contextual_query = _build_contextual_query_with_summary(original_query, history, max_turns)
    new_state["query"] = contextual_query

    # 调试：打印重构后的用户问题
    print("[query_rewrite] query_rewritten:", contextual_query)

    strategy = "summary" if contextual_query != original_query else "summary_fallback" if contextual_query != original_query else "summary_fallback"
    trace = dict(new_state.get("pipeline_trace") or {})
    trace["query_rewrite"] = {
        "query_original": original_query,
        "query_rewritten": contextual_query,
        "strategy": strategy,
        "summary_max_turns": max_turns,
    }
    new_state["pipeline_trace"] = trace

    return new_state


__all__ = [
    "query_rewrite_node",
    "_build_contextual_query",
    "_build_contextual_query_with_summary",
    "_get_last_turn_text",
    "_get_last_n_turns_text",
    "_summarize_turns",
]
