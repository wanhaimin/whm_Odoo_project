param(
    [int]$Tail = 100
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $root "runtime"
$logsDir = Join-Path $runtimeDir "logs"
$sessionFile = Join-Path $runtimeDir "session.json"
$auditFile = Join-Path $logsDir "control_audit.log"
$accessFile = Join-Path $logsDir "access.log"
$composeFile = Join-Path $root "docker-compose.yml"

Write-Host "=== Session ==="
if (Test-Path $sessionFile) {
    Get-Content $sessionFile
} else {
    Write-Host "No active session metadata."
}

Write-Host ""
Write-Host "=== Control Audit (tail $Tail) ==="
if (Test-Path $auditFile) {
    Get-Content $auditFile -Tail $Tail
} else {
    Write-Host "No control audit log."
}

Write-Host ""
Write-Host "=== Caddy Access Log (tail $Tail) ==="
if (Test-Path $accessFile) {
    Get-Content $accessFile -Tail $Tail
} else {
    Write-Host "No caddy access log yet."
}

Write-Host ""
Write-Host "=== cloudflared logs (tail $Tail) ==="
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose -f $composeFile logs cloudflared --tail $Tail --no-color
} else {
    Write-Host "Docker CLI not found."
}
