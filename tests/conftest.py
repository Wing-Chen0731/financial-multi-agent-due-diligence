from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_tests_from_local_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the deterministic test suite independent from a user's local Ollama runtime."""
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.setenv("RAG_MODE", "lexical")
