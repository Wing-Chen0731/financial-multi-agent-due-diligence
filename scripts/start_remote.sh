#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${REMOTE_ENV_FILE:-.env.remote}"
if [[ ! -f "$ENV_FILE" ]]; then
  cp .env.remote.example "$ENV_FILE"
  echo "已创建 ${ENV_FILE}，请填入 OPENROUTER_API_KEY 后重新运行。"
  exit 2
fi

if [[ ! -x .venv/bin/uvicorn ]]; then
  PYTHON_BIN="${PYTHON_BIN:-python3}"
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -e '.[rag,dev]'
fi

if ! APP_ENV_FILE="$ENV_FILE" .venv/bin/python -c '
import os
from dotenv import load_dotenv
load_dotenv(os.environ["APP_ENV_FILE"])
provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
env_file = os.environ.get("APP_ENV_FILE", ".env")
keys = {
    "openrouter": os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
    "huggingface": os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY"),
    "hf": os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY"),
}.get(provider, os.getenv("REMOTE_API_KEY") or os.getenv("OPENAI_API_KEY"))
if provider != "demo" and not keys:
    raise SystemExit(f"{env_file} 中缺少 {provider} 的 API Key。")
'; then
  exit 3
fi

PORT="${PORT:-8000}"
echo "金融 AI 工作台（远程模型，无本地模型下载）：http://127.0.0.1:${PORT}/"
echo "配置文件：${ENV_FILE}；RAG_MODE 将按该文件执行。"
exec env APP_ENV_FILE="$ENV_FILE" .venv/bin/uvicorn src.api.server:app --host 127.0.0.1 --port "$PORT"
