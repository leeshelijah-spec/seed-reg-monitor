function Get-PyVenvSetting {
    param(
        [string]$ConfigPath,
        [string]$Key
    )

    if (-not (Test-Path $ConfigPath -PathType Leaf)) {
        return $null
    }

    $prefix = "$Key = "
    $line = Get-Content $ConfigPath | Where-Object { $_.StartsWith($prefix) } | Select-Object -First 1
    if (-not $line) {
        return $null
    }

    return $line.Substring($prefix.Length).Trim().Trim('"')
}

function Test-PythonLaunchable {
    param(
        [string]$PythonExecutable
    )

    if (-not $PythonExecutable -or -not (Test-Path $PythonExecutable -PathType Leaf)) {
        return $false
    }

    try {
        & $PythonExecutable -c "import sys" 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Initialize-LocalTempDirectory {
    param(
        [string]$RepoRoot
    )

    $tempRoot = Join-Path $RepoRoot ".tmp"
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $env:TEMP = $tempRoot
    $env:TMP = $tempRoot
    $env:TMPDIR = $tempRoot
}

function Find-BasePythonCandidates {
    param(
        [string]$RepoRoot
    )

    $venvRoot = Join-Path $RepoRoot ".venv"
    $pyVenvConfig = Join-Path $venvRoot "pyvenv.cfg"
    $homeDir = Get-PyVenvSetting -ConfigPath $pyVenvConfig -Key "home"
    $configExecutable = Get-PyVenvSetting -ConfigPath $pyVenvConfig -Key "executable"
    $localPrograms = Join-Path $env:LOCALAPPDATA "Programs\Python"

    $candidates = @(
        $env:PYTHON_EXE,
        $configExecutable,
        $(if ($homeDir) { Join-Path $homeDir "python.exe" }),
        $(if ($localPrograms) { Join-Path $localPrograms "Python313\python.exe" }),
        $(if ($localPrograms) { Join-Path $localPrograms "Python312\python.exe" }),
        $(if ($localPrograms) { Join-Path $localPrograms "Python311\python.exe" }),
        $(if ($localPrograms) { Join-Path $localPrograms "Python310\python.exe" }),
        $(if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "Python313\python.exe" }),
        $(if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "Python312\python.exe" }),
        $(if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "Python311\python.exe" })
    )

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidates += $pythonCommand.Source
    }

    $pythonExeCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonExeCommand) {
        $candidates += $pythonExeCommand.Source
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        try {
            $launcherPaths = & $pyCommand.Source -0p 2>$null
            foreach ($launcherPath in $launcherPaths) {
                if ($launcherPath -and -not $launcherPath.StartsWith("-")) {
                    $candidates += $launcherPath.Trim()
                }
            }
        }
        catch {
        }
    }

    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in $candidates) {
        if (-not $candidate) {
            continue
        }

        $normalized = $candidate.Trim('"')
        if ($seen.Add($normalized)) {
            $normalized
        }
    }
}

function Find-LaunchableBasePython {
    param(
        [string]$RepoRoot
    )

    foreach ($candidate in Find-BasePythonCandidates -RepoRoot $RepoRoot) {
        if (Test-PythonLaunchable -PythonExecutable $candidate) {
            return $candidate
        }
    }

    return $null
}

function Ensure-VenvRequirements {
    param(
        [string]$BasePython,
        [string]$PythonExecutable,
        [string]$RepoRoot
    )

    try {
        & $PythonExecutable -c "import fastapi, uvicorn, apscheduler, dotenv, jinja2" 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) {
            return
        }
    }
    catch {
    }

    Write-Host "Installing dashboard dependencies into .venv..."
    & $BasePython -m pip --python $PythonExecutable install -r (Join-Path $RepoRoot "requirements.txt") | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install requirements into .venv"
    }
}

function Rebuild-VirtualEnvironment {
    param(
        [string]$RepoRoot,
        [string]$BasePython
    )

    $venvRoot = Join-Path $RepoRoot ".venv"
    Initialize-LocalTempDirectory -RepoRoot $RepoRoot

    if (Test-Path $venvRoot) {
        Write-Warning "Existing .venv is not usable. Recreating it with $BasePython"
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
    }

    Write-Host "Creating virtual environment at $venvRoot"
    & $BasePython -m venv $venvRoot --without-pip | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create .venv using $BasePython"
    }

    $venvPython = Join-Path $venvRoot "Scripts\python.exe"
    if (-not (Test-PythonLaunchable -PythonExecutable $venvPython)) {
        throw ".venv was recreated, but $venvPython is still not launchable."
    }

    Ensure-VenvRequirements -BasePython $BasePython -PythonExecutable $venvPython -RepoRoot $RepoRoot
    return $venvPython
}

function Resolve-ProjectPython {
    param(
        [string]$RepoRoot
    )

    $venvRoot = Join-Path $RepoRoot ".venv"
    $venvPython = Join-Path $venvRoot "Scripts\python.exe"
    if (Test-PythonLaunchable -PythonExecutable $venvPython) {
        $basePython = Find-LaunchableBasePython -RepoRoot $RepoRoot
        if (-not $basePython) {
            return $venvPython
        }
        Initialize-LocalTempDirectory -RepoRoot $RepoRoot
        Ensure-VenvRequirements -BasePython $basePython -PythonExecutable $venvPython -RepoRoot $RepoRoot
        return $venvPython
    }

    $basePython = Find-LaunchableBasePython -RepoRoot $RepoRoot
    if (-not $basePython) {
        throw @"
Could not find a launchable Python interpreter.
Set PYTHON_EXE to your Python path or install Python so it is reachable from PowerShell, then rerun:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_dashboard.ps1
"@
    }

    return Rebuild-VirtualEnvironment -RepoRoot $RepoRoot -BasePython $basePython
}
