$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path .venv\Scripts\python.exe) -or -not (Test-Path .env)) {
  & .\scripts\setup.ps1
}

try { Invoke-WebRequest http://127.0.0.1:11434/api/version -TimeoutSec 3 | Out-Null }
catch {
  $OllamaApp = Join-Path $env:LOCALAPPDATA "Programs\Ollama\Ollama.exe"
  if (Test-Path $OllamaApp) { Start-Process $OllamaApp }
  Start-Sleep -Seconds 5
}

Write-Host "金融 AI 工作台：http://127.0.0.1:8000/"
& .venv\Scripts\python.exe -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000
