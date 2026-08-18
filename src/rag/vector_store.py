from __future__ import annotations

import hashlib
import os
from typing import Any

from src.rag.embeddings import EmbeddingProvider, get_embedding_provider
from src.rag.loader import load_and_split


class ChromaVectorStore:
    """Persistent Chroma store with explicit local embedding providers."""

    def __init__(self, persist_dir: str | None = None, embedder: EmbeddingProvider | None = None):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("向量 RAG 需要安装 chromadb：pip install -e '.[rag]'") from exc
        self.persist_dir = persist_dir or os.getenv("RAG_PERSIST_DIR", "data/vector_db")
        self.embedder = embedder or get_embedding_provider()
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=os.getenv("RAG_COLLECTION", "financial_knowledge"),
            metadata={"hnsw:space": "cosine"},
        )

    def build(self, directory: str | None = None) -> dict[str, Any]:
        chunks = load_and_split(directory or os.getenv("KNOWLEDGE_BASE_DIR", "data/knowledge_base"))
        if not chunks:
            raise RuntimeError("知识库没有可索引的 txt、md 或 PDF 文档")
        texts = [item["text"] for item in chunks]
        embeddings = self.embedder.embed_documents(texts)
        ids = [hashlib.sha1(f"{item['metadata']['source']}:{index}".encode()).hexdigest() for index, item in enumerate(chunks)]
        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=chunks_metadata(chunks),
        )
        return {"chunks": len(chunks), "persist_dir": self.persist_dir, "collection": self.collection.name}

    def query(self, text: str, top_k: int = 4) -> list[dict[str, Any]]:
        if self.collection.count() == 0:
            raise RuntimeError("向量库为空，请先执行 python -m src.rag.cli index")
        result = self.collection.query(
            query_embeddings=[self.embedder.embed_query(text)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            {
                "source": metadata.get("source", "unknown"),
                "page": metadata.get("page"),
                "chunk": metadata.get("chunk"),
                "score": round(1 - float(distance), 4),
                "snippet": document,
                "retrieval_mode": "chroma_vector",
            }
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]


def chunks_metadata(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: ("" if value is None else str(value)) for key, value in item["metadata"].items()}
        for item in chunks
    ]
