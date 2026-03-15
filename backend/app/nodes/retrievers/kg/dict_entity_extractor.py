"""
基于本地字典的实体抽取：从问句中 N-gram 匹配词表，输出带类型的实体列表，供 KG Cypher 构造使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


@dataclass(frozen=True)
class DictEntity:
    """字典匹配得到的一条实体：text 为原文片段，types 为实体类型列表（与图谱节点标签一致）。"""
    text: str
    types: List[str]


class DictEntityExtractor:
    """
    从 dict_root 目录加载多类词表（疾病、症状、药物等），在问句中做 N-gram 滑窗匹配，返回 List[DictEntity]。
    实体类型与知识图谱节点标签一致，便于后续 Cypher 模板构造。
    """

    _DEFAULT_TYPE_FILE_MAPPING: Dict[str, str] = {
        "疾病": "disease.txt",
        "症状": "symptom.txt",
        "药物": "drug.txt",
        "食物": "food.txt",
        "生产商": "producer.txt",
        "检查手段": "check.txt",
        "一级科室": "department.txt",
        "二级科室": "department.txt",
    }

    def __init__(
        self,
        dict_root: Path,
        type_file_mapping: Dict[str, str] | None = None,
    ) -> None:
        """加载词表并构建词→类型索引与最大词长。"""
        self._dict_root = dict_root
        self._type_file_mapping = type_file_mapping or self._DEFAULT_TYPE_FILE_MAPPING
        self._word_types: Dict[str, List[str]] = {}
        self._max_len: int = 0
        self._load_dicts()

    # N-gram 滑窗匹配，从长到短；命中区间标记占用避免子串重复命中；按出现顺序去重返回。
    def extract(self, question: str) -> List[DictEntity]:
        """
        N-gram 滑窗匹配，从长到短；命中区间标记占用避免子串重复命中；按出现顺序去重返回。
        """
        text = (question or "").strip()
        if not text or not self._word_types:
            return []

        length = len(text)
        max_len = min(self._max_len, length)
        hits: List[Tuple[int, int, str]] = []
        occupied = [False] * length

        for span_len in range(max_len, 0, -1):
            for start in range(0, length - span_len + 1):
                if any(occupied[i] for i in range(start, start + span_len)):
                    continue
                span = text[start : start + span_len]
                types = self._word_types.get(span)
                if not types:
                    continue
                hits.append((start, start + span_len, span))
                for i in range(start, start + span_len):
                    occupied[i] = True

        hits.sort(key=lambda x: x[0])
        entities: List[DictEntity] = []
        seen: set[str] = set()
        for start, end, span in hits:
            if span in seen:
                continue
            seen.add(span)
            entities.append(DictEntity(text=span, types=list(self._word_types[span])))
        return entities

    # 遍历 type_file_mapping 加载词条，构建词→类型列表并统计最大词长。
    def _load_dicts(self) -> None:
        """遍历 type_file_mapping 加载词条，构建词→类型列表并统计最大词长。"""
        word_types: Dict[str, List[str]] = {}
        max_len = 0
        for entity_type, filename in self._type_file_mapping.items():
            path = self._dict_root / filename
            if not path.exists():
                continue
            for w in self._load_words(path):
                max_len = max(max_len, len(w))
                word_types.setdefault(w, []).append(entity_type)
        self._word_types = word_types
        self._max_len = max_len

    # 读取单文件词条，去空行与首尾空白。
    def _load_words(self, path: Path) -> Sequence[str]:
        """读取单文件词条，去空行与首尾空白。"""
        try:
            with path.open(encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []


__all__ = ["DictEntity", "DictEntityExtractor"]
