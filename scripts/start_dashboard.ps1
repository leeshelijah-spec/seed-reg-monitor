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

$existingListener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($existingListener) {
    $owningProcess = Get-Process -Id $existingListener.OwningProcess -ErrorAction SilentlyContinue
    $processLabel = if ($owningProcess) {
        "$($owningProcess.ProcessName) (PID $($existingListener.OwningProcess))"
    }
    else {
        "PID $($existingListener.OwningProcess)"
    }

    throw "Port $Port is already in use by $processLabel. Stop that process or run this script with -Port <different-port>."
}

$env:READ_ONLY_MODE = "false"

Set-Location $repoRoot

Write-Host "Starting dashboard in edit mode on http://$BindHost`:$Port"
& $pythonExe -m uvicorn app.main:app `
    --app-dir $repoRoot `
    --reload `
    --reload-dir $repoRoot `
    --host $BindHost `
    --port $Port
