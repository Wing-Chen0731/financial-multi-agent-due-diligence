"""LLM provider selection.

The application uses the OpenAI-compatible chat interface so it can run with a
local Ollama model or a hosted open-weight model through OpenRouter, Hugging
Face Inference Providers, DeepSeek, or another compatible gateway.  ``demo`` is
a deterministic fallback that makes the graph testable without a key or
network.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(os.getenv("APP_ENV_FILE", ".env"))


def execution_mode() -> str:
    """Return the graph execution profile: fast for daily demos, full for evaluation."""
    mode = os.getenv("AGENT_EXECUTION_MODE", "fast").lower().strip()
    return mode if mode in {"fast", "full"} else "fast"


def runtime_info() -> dict[str, str]:
    provider = os.getenv("LLM_PROVIDER", "demo").lower().strip()
    return {
        "provider": provider,
        "model": os.getenv("LLM_MODEL", "qwen3:1.7b"),
        "execution_mode": execution_mode(),
        "rag_mode": os.getenv("RAG_MODE", "auto").lower().strip(),
    }


def readiness_info() -> dict[str, Any]:
    """Check runtime dependencies without exposing credentials."""
    provider = os.getenv("LLM_PROVIDER", "demo").lower().strip()
    model = os.getenv("LLM_MODEL", "qwen3:1.7b")
    supported_providers = {
        "demo", "ollama", "openai", "openai_compatible", "deepseek",
        "openrouter", "huggingface", "hf", "remote",
    }
    checks: dict[str, Any] = {
        "provider_configured": provider in supported_providers,
        "model": model,
    }
    if provider == "demo":
        checks["provider_reachable"] = True
    elif provider == "ollama":
        checks["provider_reachable"], checks["model_available"] = _ollama_readiness(model)
    else:
        configured = bool(_api_key_for_provider(provider))
        checks["provider_reachable"] = configured
        checks["api_key_configured"] = configured
    rag_mode = os.getenv("RAG_MODE", "auto").lower().strip()
    persist_dir = os.getenv("RAG_PERSIST_DIR", "data/vector_db")
    vector_index_exists = os.path.exists(persist_dir)
    checks["rag_mode"] = rag_mode
    checks["vector_index_exists"] = vector_index_exists
    rag_ok = rag_mode in {"lexical", "auto"} or vector_index_exists
    ready = all(
        bool(value)
        for key, value in checks.items()
        if key in {"provider_configured", "provider_reachable", "model_available", "api_key_configured"}
    ) and rag_ok
    return {"status": "ready" if ready else "not_ready", "checks": checks, **runtime_info()}


def _ollama_readiness(model: str) -> tuple[bool, bool]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    root_url = base_url.removesuffix("/v1")
    try:
        response = httpx.get(f"{root_url}/api/tags", timeout=2)
        response.raise_for_status()
        models = response.json().get("models", [])
        available = any(item.get("name") == model for item in models)
        return True, available
    except (httpx.HTTPError, ValueError, TypeError):
        return False, False


class DemoLLM:
    """Small deterministic model used for smoke tests and offline demos."""

    def invoke(self, messages: list[Any]) -> Any:
        from langchain_core.messages import AIMessage

        user_text = ""
        for message in reversed(messages):
            if getattr(message, "type", None) == "human":
                user_text = str(getattr(message, "content", ""))
                break
        if "已采集数据：" in user_text:
            content = (
                "演示风险分析已完成。\n"
                "风险提示：应继续核验主体资格、现金流、债务与还款来源。\n"
                "缺失材料：当前仅有演示 CRM 资料，不能据此形成授信结论。\n"
                "下一步：补充经审计财务数据、银行流水、担保资料并提交人工复核。"
            )
        elif "检索片段：" in user_text:
            content = (
                "已基于本地检索片段完成辅助审查。\n"
                "依据范围：仅覆盖当前知识库中返回的材料。\n"
                "限制：检索结果不等于最终合规结论，仍需结合现行制度和人工复核。"
            )
        elif '"query":' in user_text:
            content = (
                "演示分析报告已生成。\n"
                "已知事实：已完成客户资料边界检查和知识库检索。\n"
                "风险提示：资料完整性、现金流、债务与还款来源仍需核验。\n"
                "下一步：补充缺失材料，由有权人员进行最终判断。"
            )
        else:
            content = (
                "这是离线演示回答：已完成问题拆解。请接入 Ollama 或 OpenAI-compatible API "
                "后获取基于模型的正式分析。当前回答不构成投资、授信或合规决定。"
            )
        return AIMessage(content=content)


def get_llm(model_name: str | None = None, temperature: float = 0.2):
    """Return the configured chat model.

    Provider selection is explicit and safe: if a required key is absent, the
    app fails with an actionable message instead of silently making a network
    call.  ``demo`` is always available once project dependencies are installed.
    """

    provider = os.getenv("LLM_PROVIDER", "demo").lower().strip()
    model = model_name or os.getenv("LLM_MODEL", "qwen3:1.7b")

    if provider == "demo":
        return DemoLLM()

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - dependency installation issue
        raise RuntimeError("缺少 langchain-openai，请先执行 pip install -e .") from exc

    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "700"))
        num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
        think = os.getenv("OLLAMA_THINK", "false").lower() in {"1", "true", "yes"}
        return ChatOpenAI(
            model=model,
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            base_url=base_url,
            temperature=temperature,
            timeout=120,
            max_retries=2,
            max_completion_tokens=max_tokens,
            extra_body={"num_ctx": num_ctx, "think": think},
        )

    if provider in {
        "openai",
        "openai_compatible",
        "deepseek",
        "openrouter",
        "huggingface",
        "hf",
        "remote",
    }:
        api_key = _api_key_for_provider(provider)
        if not api_key:
            raise RuntimeError(
                f"LLM_PROVIDER={provider} 需要对应的远程 API Key。"
                "OpenRouter 请设置 OPENROUTER_API_KEY，Hugging Face 请设置 HF_TOKEN，"
                "通用 OpenAI-compatible 请设置 OPENAI_API_KEY；"
                "不想配置 Key 可改为 LLM_PROVIDER=demo。"
            )
        base_url = _base_url_for_provider(provider)
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            timeout=120,
            max_retries=2,
        )

    raise ValueError(f"不支持的 LLM_PROVIDER: {provider}")


def _api_key_for_provider(provider: str) -> str | None:
    """Resolve provider-specific keys without requiring users to rename them."""
    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if provider in {"huggingface", "hf"}:
        return os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
    if provider == "deepseek":
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    return (
        os.getenv("REMOTE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("HF_TOKEN")
        or os.getenv("DEEPSEEK_API_KEY")
    )


def _base_url_for_provider(provider: str) -> str:
    """Resolve the endpoint while keeping the generic provider configurable."""
    if provider == "openrouter":
        return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if provider in {"huggingface", "hf"}:
        return os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1")
    if provider == "deepseek":
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    if provider == "openai":
        return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    return os.getenv("REMOTE_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
