from __future__ import annotations

import math
from typing import List

from app.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_EMBEDDING_MODEL,
    OPENAI_API_KEY1,
    OPENAI_BASE_URL,
    OPENAI_EMBEDDING_MODEL,
)

# 选择用于向量化的 阿里云百炼 兼容 Embedding 后端配置
def _pick_embedding_backend() -> tuple[str, str, str]:
    """
    选择用于向量化的 阿里云百炼 兼容 Embedding 后端配置。

    功能描述：
    根据环境变量选择实际用于 embedding 的服务与模型，优先使用 DASHSCOPE（阿里云百炼兼容模式），
    若未配置则回退到 阿里云百炼 配置，避免因默认代理不可用导致向量化一直失败。

    入参说明：
    - 无入参。

    返回值说明：
    - tuple[str, str, str]：(provider, base_url, model)：
      - provider：'dashscope' | 'openai'；
      - base_url：阿里云百炼 兼容接口 base url（不包含结尾 /）；
      - model：embedding 模型名。
    """
    dash_key_ok = (DASHSCOPE_API_KEY or "").strip()
    dash_url_ok = (DASHSCOPE_BASE_URL or "").strip()
    dash_model_ok = (DASHSCOPE_EMBEDDING_MODEL or "").strip()
    if dash_key_ok and dash_url_ok and dash_model_ok:
        return ("dashscope", dash_url_ok.rstrip("/"), dash_model_ok)

    return ("openai", "", "")

# 调用 阿里云百炼 兼容的 Embedding 接口，将文本列表转为向量列表
def _get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    调用 OpenAI 兼容的 Embedding 接口，将文本列表转为向量列表。

    入参：
    - texts：list[str]，待嵌入的文本列表。

    返回值：
    - list[list[float]]：与 texts 一一对应的向量列表。

    异常：
    - RuntimeError：未安装 openai 或接口调用失败。
    - ValueError：Embedding 配置缺失（base_url、model 或 API KEY）。
    """
    if not texts:
        return []

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("未安装 openai，无法调用 embedding 接口") from e

    provider, base_url, model = _pick_embedding_backend()
    if not base_url or not model:
        raise ValueError("Embedding 配置缺失（DASHSCOPE_* 或 OPENAI_*），请检查 base_url 与 model")

    api_key = (DASHSCOPE_API_KEY or "").strip()
    if not api_key:
        raise ValueError(f"Embedding API KEY 缺失 provider={provider}，请配置 DASHSCOPE_API_KEY 或 OPENAI_API_KEY")

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        resp = client.embeddings.create(
            model=model,
            input=texts,
        )
        return [item.embedding for item in resp.data]
    except Exception as e:
        raise RuntimeError(f"embedding 调用失败: {e}") from e

# 对向量做 L2 归一化，减少存储与检索开销并保证余弦相似度稳定
def _compress_embeddings(embeddings: List[List[float]]) -> List[List[float]]:
    """
    对向量做 L2 归一化，减少存储与检索开销并保证余弦相似度稳定。

    入参：
    - embeddings：list[list[float]]，原始向量列表。

    返回值：
    - list[list[float]]：处理后的向量列表（当前实现为 L2 归一化）。
    """
    if not embeddings:
        return []
    out: List[List[float]] = []
    for vec in embeddings:
        norm = math.sqrt(sum(x * x for x in vec))
        if norm <= 0:
            out.append(vec)
            continue
        out.append([x / norm for x in vec])
    return out


__all__ = ["_get_embeddings", "_compress_embeddings"]

