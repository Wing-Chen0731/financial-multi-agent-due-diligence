from __future__ import annotations

import os
from typing import Any, Protocol

import httpx


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbeddings:
    """Free local embeddings through Ollama's OpenAI-compatible endpoint."""

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or os.getenv("RAG_EMBEDDING_MODEL", "qwen3-embedding:0.6b")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")).rstrip("/")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": texts},
                timeout=120,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"无法调用 Ollama Embedding，请确认已执行 `ollama pull {self.model}` 且服务已启动"
            ) from exc
        payload: dict[str, Any] = response.json()
        data = payload.get("data", [])
        vectors = [item.get("embedding") for item in sorted(data, key=lambda item: item.get("index", 0))]
        if len(vectors) != len(texts) or any(not isinstance(vector, list) for vector in vectors):
            raise RuntimeError("Ollama Embedding 返回格式不正确")
        return vectors


class OpenAICompatibleEmbeddings:
    """Remote embeddings through an OpenAI-compatible ``/embeddings`` API.

    This lets the application keep vector RAG when the chat model is hosted
    remotely. The embedding model and endpoint are deliberately configurable;
    not every hosted chat provider offers embeddings or includes them in its
    free tier.
    """

    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("RAG_EMBEDDING_MODEL", "")
        self.base_url = (
            base_url
            or os.getenv("RAG_EMBEDDING_BASE_URL")
            or os.getenv("REMOTE_BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
            or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.api_key = api_key or _embedding_api_key()
        if not self.model:
            raise RuntimeError(
                "远程向量 RAG 需要设置 RAG_EMBEDDING_MODEL；如果不使用远程 Embedding，"
                "请将 RAG_MODE=lexical。"
            )
        if not self.api_key:
            raise RuntimeError(
                "远程向量 RAG 需要 RAG_EMBEDDING_API_KEY、OPENROUTER_API_KEY、"
                "HF_TOKEN 或 OPENAI_API_KEY。"
            )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
                timeout=120,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"远程 Embedding 调用失败（{self.base_url}）；请检查 endpoint、模型名、Key 和额度。"
            ) from exc
        payload: dict[str, Any] = response.json()
        data = payload.get("data", [])
        vectors = [item.get("embedding") for item in sorted(data, key=lambda item: item.get("index", 0))]
        if len(vectors) != len(texts) or any(not isinstance(vector, list) for vector in vectors):
            raise RuntimeError("远程 Embedding 返回格式不正确，应包含 data[].embedding")
        return vectors


class SentenceTransformerEmbeddings:
    """Free local Hugging Face embeddings using BGE small Chinese."""

    def __init__(self, model: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "本地 SentenceTransformer Embedding 需要安装 rag extra：pip install -e '.[rag]'"
            ) from exc
        self.model = SentenceTransformer(model or os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("RAG_EMBEDDING_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return OllamaEmbeddings()
    if provider in {"sentence_transformers", "huggingface", "local"}:
        return SentenceTransformerEmbeddings()
    if provider in {"openai", "openai_compatible", "openrouter", "remote", "huggingface_api", "hf", "hf_api"}:
        return OpenAICompatibleEmbeddings()
    raise ValueError(f"不支持的 RAG_EMBEDDING_PROVIDER: {provider}")


def _embedding_api_key() -> str | None:
    return (
        os.getenv("RAG_EMBEDDING_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("HF_TOKEN")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("REMOTE_API_KEY")
    )
