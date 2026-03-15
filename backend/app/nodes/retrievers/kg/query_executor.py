"""
执行 Neo4j Cypher 查询并返回结构化结果。

功能描述：
- 在已有 Session 或通过 connection 获取的 Session 上执行 Cypher 及参数；
- 将返回记录转为“事实”字典列表（如 fromName、relType、toName），供上层拼成 RetrievedDoc 文本。

入参说明：
- cypher：str，Cypher 语句；
- params：Dict[str, Any]，查询参数；
- database：str | None，数据库名，默认使用 config 中 NEO4J_DATABASE。

返回值说明：
- run_query(cypher, params, ...)：返回 List[Dict[str, Any]]，每条为一条记录（键为 Cypher RETURN 的别名）。
"""

from __future__ import annotations

from typing import Any, Dict, List

from .connection import session_context


def run_query(
    cypher: str,
    params: Dict[str, Any],
    *,
    database: str | None = None,
) -> List[Dict[str, Any]]:
    """
    执行 Cypher 查询并返回记录列表。

    功能描述：
    - 使用 session_context 创建 Session，执行 session.run(cypher, params)；
    - 将每条 record 转为字典（key 为 RETURN 别名），汇总为列表返回；
    - 若 Cypher 为空或执行异常，返回空列表，不向外抛异常。

    入参说明：
    - cypher：str，Cypher 语句；
    - params：Dict[str, Any]，查询参数；
    - database：str | None，Neo4j 数据库名，默认 None 表示使用配置中的库。

    返回值说明：
    - List[Dict[str, Any]]：查询结果记录列表，每条记录为键值对；无结果或异常时返回 []。
    """
    if not (cypher or "").strip():
        return []
    try:
        with session_context(database=database) as session:
            result = session.run(cypher, params)
            records: List[Dict[str, Any]] = []
            for record in result:
                records.append(dict(record))
            return records
    except RuntimeError:
        return []
    except Exception:
        return []


__all__ = ["run_query"]
