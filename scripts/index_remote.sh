#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="${REMOTE_ENV_FILE:-.env.remote}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "未找到 ${ENV_FILE}。先运行 ./scripts/start_remote.sh 创建配置模板。"
  exit 2
fi
if [[ ! -x .venv/bin/python ]]; then
  echo "未找到 Python 环境。先运行 ./scripts/start_remote.sh 安装依赖。"
  exit 2
fi

echo "开始调用远程 Embedding 并构建持久化 Chroma 向量库。"
exec env APP_ENV_FILE="$ENV_FILE" RAG_MODE=vector .venv/bin/python -m src.rag.cli index
