"""
System + Human 消息构建，供各节点组 messages 后调用 cfg.invoke_and_get_content(messages)。
"""

from __future__ import annotations


def build_system_human_messages(system_content: str, human_content: str) -> list[dict]:
    """
    构建 [system, user] 消息列表。
    入参：system_content、human_content 为已填充的字符串。
    返回：list[dict]，每项 {"role": "system"|"user", "content": str}。
    """
    return [
        {"role": "system", "content": (system_content or "").strip() or "你是一个有帮助的助手。"},
        {"role": "user", "content": (human_content or "").strip()},
    ]
