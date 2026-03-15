from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from app.config import (
    NEO4J_NODE_LABELS,
    NEO4J_RELATIONSHIP_TYPES,
    get_intent_templates,
)

from .dict_entity_extractor import DictEntity

QuestionIntent = Literal[
    "disease_diet",
    "disease_drug",
    "disease_check",
    "disease_symptom",
    "symptom_disease",
]

# 饮食意图：宜吃 / 忌吃 区分用（_diet_rels_from_question）；并集用于意图检测（SimpleIntentDetector）
_DIET_WORDS_RECOMMEND = {"宜吃", "适合吃", "能吃", "吃什么"}
_DIET_WORDS_AVOID = {"忌吃", "忌口", "不能吃"}
_DIET_WORDS_ALL = _DIET_WORDS_RECOMMEND | _DIET_WORDS_AVOID | {"饮食"}


@dataclass(frozen=True)
class IntentResult:
    """
    单次意图识别结果：实体列表 + 意图标签列表，供后续选择 Cypher 模板。
    入参：entities（字典匹配实体列表）、intents（识别出的意图标签）。无返回值。
    """

    entities: List[DictEntity]
    intents: List[QuestionIntent]


class SimpleIntentDetector:
    """
    基于触发词与实体类型的轻量意图识别器；支持疾病饮食/用药/检查/症状及症状反推疾病。
    无构造入参。detect(question, entities) 返回 IntentResult。
    """

    _DRUG_WORDS = {"吃什么药", "用药", "药物", "治疗药物"}
    _CHECK_WORDS = {"检查", "确诊", "做什么检查", "诊断", "诊断建议"}
    _SYMPTOM_WORDS = {"症状", "有哪些症状", "什么症状"}

    def __init__(self) -> None:
        self._diet_words: set[str] = _DIET_WORDS_ALL

    def detect(self, question: str, entities: Sequence[DictEntity]) -> IntentResult:
        """
        根据问句与实体类型识别意图。
        入参：question 用户问句，entities 字典实体序列。返回 IntentResult。
        """
        text = (question or "").strip()
        ent_list = list(entities)
        if not text or not ent_list:
            return IntentResult(entities=ent_list, intents=[])

        types = list(dict.fromkeys(t for e in ent_list for t in e.types))
        has_disease = "疾病" in types
        has_symptom = "症状" in types

        rules: List[Tuple[bool, QuestionIntent]] = [
            (has_disease and self._contains_any(text, self._diet_words), "disease_diet"),
            (has_disease and self._contains_any(text, self._DRUG_WORDS), "disease_drug"),
            (has_disease and self._contains_any(text, self._CHECK_WORDS), "disease_check"),
            (has_disease and self._contains_any(text, self._SYMPTOM_WORDS), "disease_symptom"),
        ]
        intents = [intent for cond, intent in rules if cond]
        if has_symptom and not intents:
            intents.append("symptom_disease")

        return IntentResult(entities=ent_list, intents=intents)

    def _contains_any(self, sent: str, words: Iterable[str]) -> bool:
        """判断 sent 中是否包含 words 中任意一词。入参：sent 句子，words 触发词可迭代。返回 bool。"""
        return any(w in sent for w in words)


def _diet_rels_from_question(question: str) -> List[str]:
    """
    根据问句判断查宜吃、忌吃或两者：仅宜吃词→宜吃，仅忌吃词→忌吃，否则两种都查。
    入参：question 用户问句。返回要使用的关类型列表，如 ["宜吃"]、["忌吃"] 或 ["宜吃", "忌吃"]。
    """
    text = (question or "").strip()
    rels: List[str] = []
    if any(w in text for w in _DIET_WORDS_RECOMMEND):
        rels.append("宜吃")
    if any(w in text for w in _DIET_WORDS_AVOID):
        rels.append("忌吃")
    return rels if rels else ["宜吃", "忌吃"]


def _build_cypher(
    match_part: str,
    from_var: str,
    to_var: str,
    param_key: str,
    param_value: str,
    search_key: str,
    max_results: int,
    where_clause: Optional[str] = None,
    extra_params: Optional[Dict[str, object]] = None,
) -> Tuple[str, Dict[str, object]]:
    """
    拼装通用「MATCH-RETURN-LIMIT」Cypher 及参数。
    入参：match_part 匹配模式，from_var/to_var 用于 RETURN，param_key/param_value 绑定参数，
         search_key/max_results 配置，where_clause 可选 WHERE 条件，extra_params 可选额外参数（如 endLabels）。
    返回：(cypher, params)。
    """
    lines = [f"MATCH {match_part}"]
    if where_clause:
        lines.append(f"WHERE {where_clause}")
    lines.append(
        f"RETURN toString({from_var}.`{search_key}`) AS fromName, "
        f"type(r) AS relType, toString({to_var}.`{search_key}`) AS toName\nLIMIT $limit"
    )
    params: Dict[str, object] = {param_key: param_value, "limit": max_results}
    if extra_params:
        params.update(extra_params)
    return "\n".join(lines), params


def build_cypher_from_intent(
    intent: QuestionIntent,
    entities: Sequence[DictEntity],
    *,
    question: Optional[str] = None,
    search_key: str = "名称",
    max_results: int = 30,
) -> Tuple[str, Dict[str, object]]:
    """
    按配置的意图模板与白名单构建 Cypher；disease_diet 时用 question 区分宜吃/忌吃。无法构造时返回 ("", {})。
    入参：intent 意图，entities 实体列表，question 可选问句，search_key 节点名称属性，max_results 上限。
    返回：(cypher, params)。
    """
    templates = get_intent_templates()
    template = templates.get(intent) if isinstance(intent, str) else None
    if not template:
        return "", {}

    # 关系类型：dynamic_rels 时按问句取子集，再与白名单取交
    rels = (
        _diet_rels_from_question(question or "")
        if template.get("dynamic_rels")
        else template.get("relationship_type") or []
    )
    allowed_rels = [r for r in rels if r in NEO4J_RELATIONSHIP_TYPES]
    if not allowed_rels:
        return "", {}

    # 起点/终点标签与白名单取交
    start_labels = [
        lbl for lbl in (template.get("start_label") or []) if lbl in NEO4J_NODE_LABELS
    ]
    end_labels = [
        lbl for lbl in (template.get("end_label") or []) if lbl in NEO4J_NODE_LABELS
    ]
    if not start_labels or not end_labels:
        return "", {}

    entity_type = template.get("entity_type") or ""
    param_key = template.get("param_key") or "disease"
    param_value = _pick_first_entity_text(entities, entity_type)
    if not param_value:
        return "", {}

    from_var, to_var = "a", "b"
    rel_pattern = "|".join(allowed_rels)
    end_multi_label = template.get("end_multi_label")

    if end_multi_label:
        match_part = (
            f"({from_var}:{start_labels[0]} {{`{search_key}`: ${param_key}}})"
            f"-[r:{rel_pattern}]->({to_var})"
        )
        where_clause = "ANY(lbl IN labels(b) WHERE lbl IN $endLabels)"
        extra_params: Dict[str, object] = {"endLabels": end_labels}
        return _build_cypher(
            match_part,
            from_var,
            to_var,
            param_key,
            param_value,
            search_key,
            max_results,
            where_clause=where_clause,
            extra_params=extra_params,
        )
    match_part = (
        f"({from_var}:{start_labels[0]} {{`{search_key}`: ${param_key}}})"
        f"-[r:{rel_pattern}]->({to_var}:{end_labels[0]})"
    )
    return _build_cypher(
        match_part,
        from_var,
        to_var,
        param_key,
        param_value,
        search_key,
        max_results,
    )


def _pick_first_entity_text(
    entities: Sequence[DictEntity],
    entity_type: str,
) -> Optional[str]:
    """从实体列表中取第一个指定类型实体的 text。入参：entities、entity_type。返回 str 或 None。"""
    for e in entities:
        if entity_type in e.types:
            return e.text
    return None


__all__ = [
    "QuestionIntent",
    "IntentResult",
    "SimpleIntentDetector",
    "build_cypher_from_intent",
]

