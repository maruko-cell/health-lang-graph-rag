"""
Neo4j 连接管理：get_driver() 返回单例 Driver 或 None，session_context() 提供 with 内 Session；
未配置或连接失败时返回 None，便于检索层降级。配置来自 app.config（NEO4J_URI、NEO4J_USER、NEO4J_PASSWORD、NEO4J_DATABASE）。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, Optional

from app.config import (
    NEO4J_DATABASE,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
)

if TYPE_CHECKING:
    import neo4j

_driver: Optional["neo4j.Driver"] = None

# 返回全局 Neo4j Driver 单例；未配置或连接失败时返回 None。
def get_driver() -> Optional["neo4j.Driver"]:
    """
    返回全局 Neo4j Driver 单例；未配置或连接失败时返回 None。
    入参：无。
    返回值：neo4j.Driver 或 None。
    """
    global _driver
    if _driver is not None:
        return _driver
    if not NEO4J_URI or not NEO4J_USER or NEO4J_PASSWORD is None:
        return None
    try:
        import neo4j

        _driver = neo4j.GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD or ""),
        )
        _driver.verify_connectivity()
        return _driver
    except Exception:
        _driver = None
        return None

# 返回 Neo4j Session 的上下文管理器，退出时自动关闭 Session。
@contextmanager
def session_context(
    database: Optional[str] = None,
) -> Generator["neo4j.Session", None, None]:
    """
    返回 Neo4j Session 的上下文管理器，退出时自动关闭 Session。
    入参：database，str | None，库名，默认用 NEO4J_DATABASE。
    返回值：yield neo4j.Session。若 get_driver() 为 None 则 raise RuntimeError。
    """
    driver = get_driver()
    if driver is None:
        raise RuntimeError("Neo4j Driver 不可用，无法创建 Session")
    db = database if database is not None else (NEO4J_DATABASE or None)
    session = driver.session(database=db)
    try:
        # 返回 Neo4j Session 的上下文管理器，退出时自动关闭 Session。
        yield session
    finally:
        session.close()


__all__ = ["get_driver", "session_context"]
