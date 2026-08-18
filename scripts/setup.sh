#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:1.7b}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-qwen3-embedding:0.6b}"

echo "[1/5] 创建 Python 环境并安装依赖"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[rag,dev]'

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

if command -v ollama >/dev/null 2>&1; then
  OLLAMA_BIN="$(command -v ollama)"
elif [[ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]]; then
  OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
else
  echo "未找到 Ollama。请先从 https://ollama.com/download 安装 Ollama，再重新运行此脚本。"
  exit 2
fi

echo "[2/5] 启动 Ollama"
if ! curl -fsS --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open -a /Applications/Ollama.app --args --hidden >/dev/null 2>&1 || true
  else
    nohup "$OLLAMA_BIN" serve >.ollama.log 2>&1 &
  fi
fi

for attempt in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" == "30" ]]; then
    echo "Ollama 服务未能在 30 秒内启动，请打开 Ollama 应用后重试。"
    exit 3
  fi
  sleep 1
done

echo "[3/5] 下载轻量级本地模型：$OLLAMA_MODEL"
"$OLLAMA_BIN" pull "$OLLAMA_MODEL"
echo "[4/5] 下载 Embedding 模型：$EMBEDDING_MODEL"
"$OLLAMA_BIN" pull "$EMBEDDING_MODEL"

echo "[5/5] 构建持久化向量库"
RAG_MODE=vector .venv/bin/python -m src.rag.cli index
echo "完成。运行 ./scripts/start.sh 启动 Web 工作台。"
