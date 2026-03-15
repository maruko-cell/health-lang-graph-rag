"""LLM 统一调用封装：create_llm_agent() 得到 cfg，常用 cfg.invoke_and_get_content(messages) 取回复文本。"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

from app.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_MODEL,
    DEFAULT_LLM,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY1,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    SILICON_API_KEY,
    ZHIPUAI_API_KEY,
    ZHIPUAI_URL,
    ZHIPUAI_MODEL,
)

DEFAULT_SYSTEM_PROMPT = "你是一个有帮助的助手。"


@dataclass
class LLMRuntimeConfig:
    """当前会话的 LLM 配置；常用 invoke_and_get_content(messages) 调用并取回复文本。"""

    provider: str
    model: str
    api_key: Optional[str]
    base_url: Optional[str]
    # 内部统一调用 Chat Completions，入参 messages 非空且已含 system。
    def _chat(self, messages: list[dict]) -> SimpleNamespace:
        """
        内部统一调用 Chat Completions，入参 messages 非空且已含 system。
        返回 SimpleNamespace(content=...)，调用失败或无 choices 时 content 为空串。
        """
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("未安装 openai 依赖，无法调用 Chat Completions") from e
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
            content = (
                (getattr(resp.choices[0].message, "content", None) or "").strip()
                if (resp and getattr(resp, "choices", None))
                else ""
            )
            return SimpleNamespace(content=content)
        except Exception as e:
            raise RuntimeError(f"LLM 调用失败: {e}") from e
    
    # 将 messages 发给 LLM，返回 SimpleNamespace(content=...)。
    def invoke_llm(self, messages: list[dict]) -> SimpleNamespace:
        """
        统一调用入口：将 messages 发给 LLM，返回 SimpleNamespace(content=...)。
        若 messages 为空则直接返回 content 为空；若首条不是 system 则自动在头部插入默认 system。
        """
        if not messages:
            return SimpleNamespace(content="")
        normalized = (
            [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, *messages]
            if messages[0].get("role") != "system"
            else list(messages)
        )
        return self._chat(normalized)
   
    # 从 invoke_llm 返回值取出 content 并 strip，空则返回 default。
    def get_llm_content(self, resp: SimpleNamespace, default: str = "") -> str:
        """从 invoke_llm 返回值取出 content 并 strip，空则返回 default。"""
        return (getattr(resp, "content", None) or "").strip() or default
    
    # 调用 LLM 并直接返回回复文本，空或失败时返回 default。
    def invoke_and_get_content(self, messages: list[dict], default: str = "") -> str:
        """调用 LLM 并直接返回回复文本，空或失败时返回 default。"""
        return self.get_llm_content(self.invoke_llm(messages), default=default)


def create_llm_agent(
    default_llm: Optional[str] = DEFAULT_LLM,
    default_model: Optional[str] = OLLAMA_MODEL,
) -> LLMRuntimeConfig:
    """根据环境变量与入参返回 LLM 配置，供上层调用 cfg.invoke_and_get_content(messages)。"""
    provider = (default_llm or "ollama").lower()

    match provider:
        case "openai":
            return LLMRuntimeConfig(
                provider="openai",
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY1,
                base_url=OPENAI_BASE_URL,
            )
        case "dashscope":
            return LLMRuntimeConfig(
                provider="dashscope",
                model=DASHSCOPE_MODEL,
                api_key=DASHSCOPE_API_KEY,
                base_url=DASHSCOPE_BASE_URL,
            )
        case "zhipu":
            return LLMRuntimeConfig(
                provider="zhipu",
                model=ZHIPUAI_MODEL,
                api_key=ZHIPUAI_API_KEY,
                base_url=ZHIPUAI_URL,
            )
        case "silicon":
            return LLMRuntimeConfig(
                provider="silicon",
                model="silicon-gpt",
                api_key=SILICON_API_KEY,
                base_url=None,
            )
        case _:
            model_name = default_model or OLLAMA_MODEL
            return LLMRuntimeConfig(
                provider="ollama",
                model=model_name,
                api_key="ollama",
                base_url=OLLAMA_BASE_URL,
            )
