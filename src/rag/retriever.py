from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.rag.loader import load_and_split


def _tokens(text: str) -> set[str]:
    chinese_chars = re.findall(r"[一-鿿]", text)
    chinese = {"".join(chinese_chars[index : index + 2]) for index in range(len(chinese_chars) - 1)}
    words = set(re.findall(r"[A-Za-z0-9_]+", text.lower()))
    return chinese | words


def load_knowledge_base(directory: str = "data/knowledge_base") -> list[dict[str, Any]]:
    """Load txt/md files without requiring an embedding service.

    PDF support is optional: if pypdf is installed, text is extracted; otherwise
    the caller receives a clear message and can use txt/md files.
    """
    root = Path(directory)
    documents: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8")
            documents.append({"source": str(path), "text": text})
        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader
                text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
                documents.append({"source": str(path), "text": text})
            except ImportError:
                continue
    return documents


def retrieve(query: str, directory: str = "data/knowledge_base", top_k: int = 4) -> list[dict[str, Any]]:
    """Return the most lexically relevant snippets with transparent scores."""
    query_tokens = _tokens(query)
    scored: list[dict[str, Any]] = []
    for document in load_and_split(directory):
        text = document["text"]
        tokens = _tokens(text)
        overlap = len(query_tokens & tokens)
        if overlap == 0:
            continue
        scored.append({
            "source": document["metadata"]["source"],
            "page": document["metadata"]["page"],
            "chunk": document["metadata"]["chunk"],
            "score": overlap,
            "snippet": text,
            "retrieval_mode": "lexical",
        })
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]
