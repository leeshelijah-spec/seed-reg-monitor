param(
    [int]$Port = 8010,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

$env:READ_ONLY_MODE = "true"

Set-Location $repoRoot

Write-Host "Starting read-only dashboard on http://$BindHost`:$Port"
& $pythonExe -m uvicorn app.main:app --reload --host $BindHost --port $Port
