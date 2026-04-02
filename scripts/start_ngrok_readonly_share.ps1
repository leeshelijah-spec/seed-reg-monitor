param(
    [string]$NgrokAuthtoken,
    [string]$Username = "viewer",
    [string]$Password,
    [int]$Port = 8010,
    [switch]$DisableBasicAuth
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$ngrokExe = Join-Path $repoRoot ".tools\ngrok\ngrok.exe"
$policyPath = Join-Path $repoRoot "config\ngrok-readonly-policy.local.yml"
$configDir = Join-Path $env:LOCALAPPDATA "ngrok"
$configPath = Join-Path $configDir "ngrok.yml"

if (-not (Test-Path $ngrokExe)) {
    throw "ngrok executable not found at $ngrokExe"
}

if (-not $DisableBasicAuth -and -not $Password) {
    $Password = "{0}!{1}" -f ([guid]::NewGuid().ToString("N").Substring(0, 12)), (Get-Random -Minimum 1000 -Maximum 9999)
}

if ($NgrokAuthtoken) {
    & $ngrokExe config add-authtoken $NgrokAuthtoken | Out-Host
} elseif (-not (Test-Path $configPath) -and -not $env:NGROK_AUTHTOKEN) {
    throw "No ngrok authtoken found. Pass -NgrokAuthtoken or run '.tools\\ngrok\\ngrok.exe config add-authtoken <token>' first."
}

$policyLines = @(
"on_http_request:"
)

if (-not $DisableBasicAuth) {
    $policyLines += @(
"  - name: Require basic auth for the shared dashboard"
"    actions:"
"      - type: basic-auth"
"        config:"
"          credentials:"
"            - ""$Username`:$Password"""
    )
}

$policyLines += @(
"  - name: Block write methods before they reach the app"
"    expressions:"
"      - req.method != 'GET' && req.method != 'HEAD'"
"    actions:"
"      - type: deny"
"        config:"
"          status_code: 403"
)

$policy = $policyLines -join "`r`n"

Set-Content -LiteralPath $policyPath -Value $policy -Encoding UTF8

Set-Location $repoRoot

Write-Host ""
Write-Host "Read-only sharing policy created at: $policyPath"
if ($DisableBasicAuth) {
    Write-Host "Basic auth: disabled"
} else {
    Write-Host "Share URL auth username: $Username"
    Write-Host "Share URL auth password: $Password"
}
Write-Host ""
Write-Host "Starting ngrok on port $Port..."
Write-Host ""

& $ngrokExe http $Port --traffic-policy-file $policyPath
