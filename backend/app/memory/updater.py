"""
图外更新模块：根据本轮对话（及可选多模态结果）抽取长期事实与用户画像并写入 Redis。

功能描述：
在图执行完成后由路由调用；调用 LLM 抽取 facts 与 profile，再调用 long_term.add_facts、
profile.update_profile。不访问短期记忆；抽取失败时不抛错。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.config import LONG_TERM_MEMORY_ENABLED, PROFILE_UPDATE_ENABLED
from app.memory.long_term import add_facts as _add_facts
from app.memory.profile import update_profile as _update_profile

# 从 LLM 回复中解析出 JSON 对象；兼容被 markdown 包裹的情况。
def _extract_json_from_response(content: str) -> Optional[Dict[str, Any]]:
    """
    从 LLM 回复中解析出 JSON 对象；兼容被 markdown 包裹的情况。

    入参：content，str，LLM 返回的文本。
    返回值：dict 或 None。
    """
    text = (content or "").strip()
    if not text:
        return None
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取 ```json ... ``` 或 {...}
    for pattern in (r"```(?:json)?\s*([\s\S]*?)\s*```", r"(\{[\s\S]*\})"):
        m = re.search(pattern, text)
        if m:
            raw = m.group(1).strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                continue
    return None

# 根据本轮对话抽取长期事实与用户画像并写入 Redis；在图执行完成后调用。
def update_after_turn(
    user_id: str,
    session_id: str,
    query: str,
    reply: str,
    multi_moda_insight: Optional[str] = None,
) -> None:
    """
    根据本轮对话抽取长期事实与用户画像并写入 Redis；在图执行完成后调用。

    入参：
    - user_id：str，用户标识。
    - session_id：str，会话标识（作为事实来源）。
    - query：str，用户本条消息。
    - reply：str，助手本条回复。
    - multi_moda_insight：str | None，本轮多模态解读结果（若有）。

    返回值：无返回值。
    关键逻辑：若未开启长期/画像则 return；构造 prompt 调 LLM；解析出 facts 与 profile 后
    调用 long_term.add_facts、profile.update_profile；异常静默跳过。
    """
    if not (LONG_TERM_MEMORY_ENABLED or PROFILE_UPDATE_ENABLED):
        return
    if not (user_id and str(user_id).strip()):
        return
    from app.common.Prompt import MEMORY_EXTRACT_HUMAN, MEMORY_EXTRACT_SYSTEM
    from app.common.prompt_utils import build_system_human_messages
    from app.llm_agent.agent import create_llm_agent

    multi_moda_insight_optional = (multi_moda_insight or "").strip() or "（无）"
    human_content = MEMORY_EXTRACT_HUMAN.format(
        user_message=query or "",
        assistant_reply=reply or "",
        multi_moda_insight_optional=multi_moda_insight_optional,
    )
    try:
        cfg = create_llm_agent()
        messages = build_system_human_messages(MEMORY_EXTRACT_SYSTEM, human_content)
        content = cfg.invoke_and_get_content(messages)
    except Exception:
        return

    data = _extract_json_from_response(content)
    if not data:
        return

    if LONG_TERM_MEMORY_ENABLED:
        facts_raw = data.get("facts")
        if isinstance(facts_raw, list) and facts_raw:
            new_facts: List[Dict[str, Any]] = []
            for f in facts_raw:
                if isinstance(f, dict) and (f.get("text") or "").strip():
                    new_facts.append({
                        "text": (f.get("text") or "").strip(),
                        "type": (f.get("type") or "other").strip(),
                        "source": session_id,
                    })
            if new_facts:
                try:
                    _add_facts(user_id, new_facts, source=session_id)
                except Exception:
                    pass

    if PROFILE_UPDATE_ENABLED:
        profile_raw = data.get("profile")
        if isinstance(profile_raw, dict) and profile_raw:
            partial: Dict[str, Any] = {}
            for k in ("age", "gender", "height_cm", "weight_kg", "chronic_diseases", "allergies", "medications"):
                if k not in profile_raw:
                    continue
                v = profile_raw[k]
                if v is None:
                    continue
                if k in ("chronic_diseases", "allergies", "medications") and not isinstance(v, list):
                    partial[k] = [v] if v else []
                else:
                    partial[k] = v
            if partial:
                try:
                    _update_profile(user_id, partial)
                except Exception:
                    pass
