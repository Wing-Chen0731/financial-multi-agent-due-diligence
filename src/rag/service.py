from __future__ import annotations

import os
from typing import Any

from src.rag.retriever import retrieve as lexical_retrieve
from src.rag.vector_store import ChromaVectorStore


def build_vector_index(directory: str | None = None, persist_dir: str | None = None) -> dict[str, Any]:
    return ChromaVectorStore(persist_dir=persist_dir).build(directory=directory)


def retrieve_context(
    query: str,
    directory: str | None = None,
    persist_dir: str | None = None,
    top_k: int = 4,
) -> list[dict[str, Any]]:
    mode = os.getenv("RAG_MODE", "auto").lower()
    lexical_directory = directory or os.getenv("KNOWLEDGE_BASE_DIR", "data/knowledge_base")
    if mode == "lexical":
        return lexical_retrieve(query, lexical_directory, top_k)
    try:
        vector_results = ChromaVectorStore(persist_dir=persist_dir).query(query, top_k=top_k)
        if mode == "vector":
            return vector_results
        lexical_results = lexical_retrieve(query, lexical_directory, top_k)
        return _merge_results(vector_results, lexical_results, top_k)
    except (RuntimeError, ImportError):
        if mode == "vector":
            raise
        results = lexical_retrieve(query, lexical_directory, top_k)
        for result in results:
            result["retrieval_mode"] = "lexical_fallback"
        return results


def _merge_results(
    vector_results: list[dict[str, Any]],
    lexical_results: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Fuse semantic similarity and lexical overlap into a transparent score."""
    merged: dict[tuple[str, Any, Any], dict[str, Any]] = {}
    max_lexical = max((float(item.get("score", 0)) for item in lexical_results), default=1.0)
    for item in vector_results:
        key = (str(item.get("source", "")), str(item.get("page") or ""), str(item.get("chunk") or ""))
        merged[key] = {**item, "_vector_score": float(item.get("score", 0)), "_lexical_score": 0.0}
    for item in lexical_results:
        key = (str(item.get("source", "")), str(item.get("page") or ""), str(item.get("chunk") or ""))
        current = merged.setdefault(key, {**item, "_vector_score": 0.0})
        current["_lexical_score"] = float(item.get("score", 0)) / max_lexical
        current["snippet"] = current.get("snippet") or item.get("snippet", "")
    for item in merged.values():
        item["score"] = round(0.7 * item.pop("_vector_score") + 0.3 * item.pop("_lexical_score"), 4)
        item["retrieval_mode"] = "hybrid"
    return sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:top_k]
