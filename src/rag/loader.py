from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = max(
                normalized.rfind("\n\n", start, end),
                normalized.rfind("。", start, end),
                normalized.rfind("；", start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(end - chunk_overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def load_and_split(
    directory: str = "data/knowledge_base",
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[dict[str, Any]]:
    """Load supported files and create metadata-rich chunks for indexing."""
    root = Path(directory)
    chunks: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        pages: list[tuple[int | None, str]] = []
        if suffix in {".txt", ".md"}:
            pages = [(None, path.read_text(encoding="utf-8"))]
        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise RuntimeError("解析 PDF 需要安装 pypdf：pip install -e '.[rag]'") from exc
            pages = [(index + 1, page.extract_text() or "") for index, page in enumerate(PdfReader(str(path)).pages)]
        else:
            continue
        for page_number, page_text in pages:
            for chunk_index, content in enumerate(_split_text(page_text, chunk_size, chunk_overlap)):
                chunks.append({
                    "text": content,
                    "metadata": {
                        "source": str(path),
                        "file_name": path.name,
                        "page": page_number,
                        "chunk": chunk_index,
                    },
                })
    return chunks
