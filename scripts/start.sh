#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "${1:-}" == "--demo" ]]; then
  PORT="${PORT:-8000}"
  if [[ ! -x .venv/bin/python ]]; then
    PYTHON_BIN="${PYTHON_BIN:-python3}"
    "$PYTHON_BIN" -m venv .venv
    .venv/bin/python -m pip install -e '.[dev]'
  fi
  echo "金融 AI 工作台（Demo 模式）：http://127.0.0.1:${PORT}/"
  exec env LLM_PROVIDER=demo AGENT_EXECUTION_MODE=fast RAG_MODE=lexical .venv/bin/uvicorn src.api.server:app --host 127.0.0.1 --port "$PORT"
fi

if [[ ! -x .venv/bin/python || ! -f .env ]]; then
  bash scripts/setup.sh
fi

if command -v ollama >/dev/null 2>&1; then
  OLLAMA_BIN="$(command -v ollama)"
elif [[ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]]; then
  OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
else
  echo "未找到 Ollama。请安装 Ollama 后重试；如果只想先看作品，运行 ./scripts/start.sh --demo。"
  exit 2
fi

if ! curl -fsS --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open -a /Applications/Ollama.app --args --hidden >/dev/null 2>&1 || true
  else
    nohup "$OLLAMA_BIN" serve >.ollama.log 2>&1 &
  fi
  for attempt in $(seq 1 30); do
    curl -fsS --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1 && break
    [[ "$attempt" == "30" ]] && { echo "Ollama 服务未启动。"; exit 3; }
    sleep 1
  done
fi

PORT="${PORT:-8000}"
echo "金融 AI 工作台：http://127.0.0.1:${PORT}/"
exec .venv/bin/uvicorn src.api.server:app --host 127.0.0.1 --port "$PORT"
