param(
    [int]$DelayMinutes = 0,
    [string]$Reason = "manual",
    [switch]$KeepRuntimeFiles
)

$ErrorActionPreference = "Stop"

if ($DelayMinutes -gt 0) {
    Start-Sleep -Seconds ($DelayMinutes * 60)
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $root "runtime"
$logsDir = Join-Path $runtimeDir "logs"
$composeFile = Join-Path $root "docker-compose.yml"
$sessionFile = Join-Path $runtimeDir "session.json"
$auditFile = Join-Path $logsDir "control_audit.log"

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose -f $composeFile down 2>$null | Out-Null
}

"$(Get-Date -Format s) STOP reason=$Reason" | Add-Content -Path $auditFile -Encoding UTF8

if (-not $KeepRuntimeFiles) {
    if (Test-Path $sessionFile) {
        Remove-Item -Force $sessionFile
    }
}

Write-Host "Claw exposure stopped. reason=$Reason"
