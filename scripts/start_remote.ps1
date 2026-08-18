$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$envFile = if ($env:REMOTE_ENV_FILE) { $env:REMOTE_ENV_FILE } else { ".env.remote" }
if (-not (Test-Path $envFile)) {
    Copy-Item ".env.remote.example" $envFile
    Write-Host "已创建 $envFile，请填入 OPENROUTER_API_KEY 后重新运行。"
    exit 2
}

if (-not (Test-Path ".venv\Scripts\uvicorn.exe")) {
    $python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
    & $python -m venv .venv
    & .venv\Scripts\python.exe -m pip install --upgrade pip
    & .venv\Scripts\python.exe -m pip install -e ".[rag,dev]"
}

$env:APP_ENV_FILE = $envFile
$port = if ($env:PORT) { $env:PORT } else { "8000" }
Write-Host "金融 AI 工作台（远程模型，无本地模型下载）：http://127.0.0.1:$port/"
& .venv\Scripts\uvicorn.exe src.api.server:app --host 127.0.0.1 --port $port
