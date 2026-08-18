$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw "未找到 Python 3.10+，请先安装 Python。" }

python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[rag,dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

$Ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $Ollama) { throw "未找到 Ollama，请先从 https://ollama.com/download 安装。" }

try { Invoke-WebRequest http://127.0.0.1:11434/api/version -TimeoutSec 3 | Out-Null }
catch {
  $OllamaApp = Join-Path $env:LOCALAPPDATA "Programs\Ollama\Ollama.exe"
  if (Test-Path $OllamaApp) { Start-Process $OllamaApp }
  Start-Sleep -Seconds 5
}

ollama pull qwen3:1.7b
ollama pull qwen3-embedding:0.6b
$env:RAG_MODE = "vector"
.venv\Scripts\python.exe -m src.rag.cli index
Write-Host "完成。运行 .\scripts\start.ps1 启动 Web 工作台。"
