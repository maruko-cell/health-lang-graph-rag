"""
用户意图识别：当前由 LLM 将 query 分类为固定意图并映射到路由；后续可替换为小模型。

入参：recognize_route(query) 接收用户文本。
返回值：路由名，与 super 图 add_conditional_edges 的 key 一致。
"""

from __future__ import annotations

import re
from typing import List, Optional

from app.common.Prompt import INTENT_HUMAN_TEMPLATE, INTENT_SYSTEM
from app.common.prompt_utils import build_system_human_messages

# 意图标签与路由映射（扩展时在此追加）与路由映射（扩展时在此追加）
INTENT_LABELS: List[str] = [
    "地图导航",
    "看图识图",
    "运动健身",
    "饮食计划",
    "医学知识问答",
    "自画像",
    "其他",
]
INTENT_TO_ROUTE: dict[str, str] = {
    "地图导航": "surround_amap_maps_mcp",
    "看图识图": "multi_moda",
    "运动健身": "exercise",
    "饮食计划": "diet",
    "医学知识问答": "rag",
    "自画像": "selfie",
    "其他": "default",
}
DEFAULT_ROUTE = "default"

def _build_human_content(query: str) -> str:
    """用 query 与意图列表拼 Human 段内容。"""
    intent_list_str = "、".join(INTENT_LABELS)
    return INTENT_HUMAN_TEMPLATE.format(
        query=(query or "").strip() or "（无内容）",
        intent_list=intent_list_str,
    )

# 从模型输出中解析意图标签，无法匹配则返回「其他」
def _parse_intent(raw: str) -> str:
    """从模型输出中解析意图标签，无法匹配则返回「其他」。"""
    text = (raw or "").strip()
    text = re.sub(r"^[^\w\u4e00-\u9fff]*", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]*$", "", text)
    if not text:
        return "其他"
    for label in INTENT_LABELS:
        if label in text or text in label:
            return label
    return "其他"

# 调用当前意图模型得到意图标签；后续可在此处改为小模型推理。
def _predict_intent(query: str) -> Optional[str]:
    """
    调用当前意图模型得到意图标签；后续可在此处改为小模型推理。
    入参：query。返回值：意图标签或 None。
    """
    if not (query or "").strip():
        return None
    try:
        from app.llm_agent.agent import create_llm_agent

        cfg = create_llm_agent()
        messages = build_system_human_messages(INTENT_SYSTEM, _build_human_content(query))
        content = cfg.invoke_and_get_content(messages)
        return _parse_intent(content)
    except Exception:
        return None

# 根据用户问题返回路由名；识别失败时返回 DEFAULT_ROUTE
def recognize_route(query: str) -> str:
    """根据用户问题返回路由名；识别失败时返回 DEFAULT_ROUTE。"""
    intent = _predict_intent((query or "").strip())
    return INTENT_TO_ROUTE.get(intent, DEFAULT_ROUTE) if intent else DEFAULT_ROUTE


__all__ = ["INTENT_LABELS", "INTENT_TO_ROUTE", "DEFAULT_ROUTE", "recognize_route"]
