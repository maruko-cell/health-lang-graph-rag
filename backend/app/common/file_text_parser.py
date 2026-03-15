"""
文件解析工具：从字节流按后缀抽取纯文本（PDF/Word/文本），供知识库向量化等场景复用。
"""

from __future__ import annotations

from io import BytesIO

import docx
import pypdf

# 从 pypdf.PdfReader 逐页抽取文本并拼接
def _extract_pdf_text(reader: pypdf.PdfReader) -> str:
    """
    从 pypdf.PdfReader 逐页抽取文本并拼接。

    入参：reader，已打开的 PdfReader 实例。
    返回值：str，用双换行拼接的全文；无内容时为空字符串。
    """
    parts = [t for p in reader.pages if (t := p.extract_text())]
    return "\n\n".join(parts).strip()

# 从 python-docx Document 抽取段落文本并拼接
def _extract_docx_text(doc: docx.Document) -> str:
    """
    从 python-docx Document 抽取段落文本并拼接。

    入参：doc，已打开的 Document 实例。
    返回值：str，用双换行拼接的全文；无内容时为空字符串。
    """
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(parts).strip()

# 根据后缀从字节流解析 PDF、Word、纯文本，返回全文纯文本
def parse_text_from_bytes(data: bytes, suffix: str) -> str:
    """
    根据后缀从字节流解析 PDF、Word、纯文本，返回全文纯文本。

    入参：
    - data：bytes，文件二进制内容；
    - suffix：str，文件后缀（如 .pdf、.docx），用于选择解析器。

    返回值：str，解析得到的纯文本；无法解析或依赖缺失时返回空字符串。
    关键逻辑：.pdf 用 pypdf 从 BytesIO 读；.docx/.doc 用 python-docx；其余按 UTF-8 解码。
    """
    suffix = (suffix or "").lower()
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    try:
        match suffix:
            case ".pdf":
                return _extract_pdf_text(pypdf.PdfReader(BytesIO(data)))
            case ".docx" | ".doc":
                return _extract_docx_text(docx.Document(BytesIO(data)))
            case _:
                return data.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""
