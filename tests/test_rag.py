from pathlib import Path

from src.rag.embeddings import OpenAICompatibleEmbeddings
from src.rag.loader import load_and_split
from src.rag.service import retrieve_context
from src.tools.financial_tools import calculate_financial_ratios


def test_loader_creates_metadata_rich_chunks(tmp_path: Path):
    document = tmp_path / "policy.txt"
    document.write_text("授信审查需要核验主体资格。" * 100, encoding="utf-8")
    chunks = load_and_split(str(tmp_path), chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    assert chunks[0]["metadata"]["file_name"] == "policy.txt"
    assert chunks[0]["metadata"]["chunk"] == 0


def test_auto_mode_has_explicit_lexical_fallback(tmp_path: Path, monkeypatch):
    document = tmp_path / "policy.txt"
    document.write_text("授信审查需要核验主体资格。", encoding="utf-8")
    monkeypatch.setenv("RAG_MODE", "auto")
    results = retrieve_context("授信审查", directory=str(tmp_path), persist_dir=str(tmp_path / "vectors"))
    assert results
    assert results[0]["retrieval_mode"] in {"lexical", "lexical_fallback", "chroma_vector"}


def test_remote_embedding_uses_openai_compatible_endpoint(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"index": 1, "embedding": [0.2, 0.3]},
                    {"index": 0, "embedding": [0.1, 0.4]},
                ]
            }

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr("src.rag.embeddings.httpx.post", fake_post)
    provider = OpenAICompatibleEmbeddings(
        model="qwen-embedding-demo",
        base_url="https://provider.example/v1",
        api_key="test-key",
    )

    assert provider.embed_documents(["a", "b"]) == [[0.1, 0.4], [0.2, 0.3]]
    assert calls[0][0] == "https://provider.example/v1/embeddings"
    assert calls[0][1]["headers"] == {"Authorization": "Bearer test-key"}


def test_ratio_tool_rejects_zero_revenue():
    result = calculate_financial_ratios(revenue_wan=0, profit_wan=10)
    assert "收入不能为 0" in result["error"]
