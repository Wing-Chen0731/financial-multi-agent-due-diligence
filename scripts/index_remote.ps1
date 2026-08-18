$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$envFile = if ($env:REMOTE_ENV_FILE) { $env:REMOTE_ENV_FILE } else { ".env.remote" }
if (-not (Test-Path $envFile)) { throw "未找到 $envFile。先运行 .\scripts\start_remote.ps1" }
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "未找到 Python 环境。先运行 .\scripts\start_remote.ps1" }
$env:APP_ENV_FILE = $envFile
$env:RAG_MODE = "vector"
& .venv\Scripts\python.exe -m src.rag.cli index
