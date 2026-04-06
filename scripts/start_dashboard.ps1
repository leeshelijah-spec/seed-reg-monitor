param(
    [int]$Port = 8010,
    [string]$BindHost = "127.0.0.1",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$pythonResolver = Join-Path $scriptDir "resolve_python.ps1"

if (-not (Test-Path $pythonResolver -PathType Leaf)) {
    throw "Python resolver script not found at $pythonResolver"
}

. $pythonResolver

$pythonExe = Resolve-ProjectPython -RepoRoot $repoRoot

if (-not (Test-Path $pythonExe -PathType Leaf)) {
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

Set-Location $repoRoot

function Invoke-StartupSync {
    param(
        [string]$PythonExecutable
    )

    Write-Host ""
    Write-Host "Application startup complete detected. Running one-time regulation/news sync..."

    & $PythonExecutable -m app.manual_sync
    $syncExitCode = $LASTEXITCODE

    if ($syncExitCode -ne 0) {
        Write-Warning "One-time startup sync exited with code $syncExitCode."
    }
    else {
        Write-Host "One-time startup sync finished."
    }

    Write-Host ""
}

if ($Reload) {
    Write-Host "Starting dashboard with live reload on http://$BindHost`:$Port"
}
else {
    Write-Host "Starting dashboard on http://$BindHost`:$Port"
}
$startupSyncTriggered = $false
$uvicornArgs = @(
    "-m", "uvicorn",
    "app.main:app",
    "--app-dir", $repoRoot,
    "--host", $BindHost,
    "--port", $Port
)

if ($Reload) {
    $uvicornArgs += @("--reload", "--reload-dir", $repoRoot)
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"

try {
    & $pythonExe @uvicornArgs 2>&1 | ForEach-Object {
            $line = [string]$_
            Write-Host $line

            # Only run the post-start sync once per script launch, even if --reload restarts the app.
            if (-not $startupSyncTriggered -and $line -like "*Application startup complete*") {
                $startupSyncTriggered = $true
                Invoke-StartupSync -PythonExecutable $pythonExe
            }
        }
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

$uvicornExitCode = $LASTEXITCODE
if ($uvicornExitCode -ne 0) {
    exit $uvicornExitCode
}
