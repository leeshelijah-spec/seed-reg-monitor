Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$profilePath = $PROFILE.CurrentUserCurrentHost
$profileDir = Split-Path -Parent $profilePath

if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}
if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

$marker = "# seed-reg-monitor refinelogic command"
$block = @"
$marker
function /refinelogic {
    & '$projectRoot\refinelogic.cmd' @args
}
"@

$existing = if (Test-Path $profilePath) {
    Get-Content -Path $profilePath -Raw -Encoding UTF8
} else {
    ""
}
if ($existing -notlike "*$marker*") {
    $newContent = if ([string]::IsNullOrWhiteSpace($existing)) {
        $block
    } else {
        if (-not $existing.EndsWith("`n")) {
            $existing = "$existing`r`n"
        }
        "$existing$block"
    }
    Set-Content -Path $profilePath -Value $newContent -Encoding UTF8
}

. $profilePath
Write-Host "Registered /refinelogic command in $profilePath"
