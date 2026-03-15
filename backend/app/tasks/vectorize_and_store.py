"""
知识库文件向量化并写入 Chroma 持久化存储。

入参：由调用方（如 upload 路由通过 add_task）传入 url、file_id。
返回值：无返回值；异常时不向外抛以免影响后台任务队列。
关键逻辑：按 URL 下载文件 → 解析为文本 → 分块 → 调 embedding API → Chroma 写入；
         支持向量压缩（通过使用较小维度 embedding 模型或量化，见配置与注释）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import chromadb
import httpx
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.common.embeddings import _compress_embeddings, _get_embeddings
from app.common.file_text_parser import parse_text_from_bytes
from app.config import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR
from app.tasks.vectorization_status import set_vectorization_status

# 默认分块参数，兼顾检索质量与向量规模
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50

# 按文件 URL 下载、解析、分块、向量化并写入 Chroma 持久化 collection，供 RAG 检索使用
def vectorize_and_store(
    url: str,
    file_id: str = "",
    *,
    collection_name: str | None = None,
    persist_dir: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> None:
    """
    按文件 URL 下载、解析、分块、向量化并写入 Chroma 持久化 collection，供 RAG 检索使用。

    入参：
    - url：str，文件公网 URL（如 OSS 地址），会先下载再解析；
    - file_id：str，文件唯一标识，用于 metadata 过滤与去重；
    - collection_name、persist_dir、chunk_size、chunk_overlap：可选，同原逻辑。

    返回值：无返回值。
    关键逻辑：httpx 下载 URL → parse_text_from_bytes 解析 → 分块 → embedding → 写 Chroma。
    """
    if not file_id:
        return
    if not url or not url.strip():
        set_vectorization_status(file_id, "failed", 0)
        return

    collection_name = collection_name or CHROMA_COLLECTION_NAME
    persist_dir = persist_dir or CHROMA_PERSIST_DIR

    try:
        resp = httpx.get(url, timeout=60.0)
        resp.raise_for_status()
        data = resp.content
    except Exception:
        set_vectorization_status(file_id, "failed", 0)
        return

    suffix = Path(urlparse(url).path).suffix or ""
    text = parse_text_from_bytes(data, suffix)
    source_name = Path(urlparse(url).path).name or "kb_file"

    if not text.strip():
        set_vectorization_status(file_id, "failed", 0)
        return

    set_vectorization_status(file_id, "processing", 15)

    # 分块
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
    )
    chunks = splitter.split_text(text)
    if not chunks:
        set_vectorization_status(file_id, "failed", 0)
        return

    # 向量化
    set_vectorization_status(file_id, "processing", 25)
    embeddings = _get_embeddings(chunks)
    if len(embeddings) != len(chunks):
        set_vectorization_status(file_id, "failed", 0)
        return
    # 对向量做压缩/归一化
    set_vectorization_status(file_id, "processing", 80)
    embeddings = _compress_embeddings(embeddings)

    try:
        client = chromadb.PersistentClient(path=persist_dir)
        coll = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        coll.delete(where={"file_id": file_id})
        ids = [f"{file_id}_{i}" for i in range(len(chunks))]
        metadatas: list[dict[str, Any]] = [
            {"file_id": file_id, "source": source_name, "chunk_index": i}
            for i in range(len(chunks))
        ]
        try:
            coll.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
            )
        except Exception as e:
            msg = str(e)
            is_dim_mismatch = "dimension" in msg.lower() and "expect" in msg.lower()
            if is_dim_mismatch and embeddings and isinstance(embeddings[0], list):
                dim = len(embeddings[0])
                alt_collection_name = f"{collection_name}__dim{dim}"
                alt = client.get_or_create_collection(name=alt_collection_name, metadata={"hnsw:space": "cosine"})
                alt.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
                coll = alt
            else:
                raise
        set_vectorization_status(file_id, "done", 100)
    except Exception as e:
        set_vectorization_status(file_id, "failed", 0)
        raise RuntimeError(f"写入 Chroma 失败: {e}") from e

