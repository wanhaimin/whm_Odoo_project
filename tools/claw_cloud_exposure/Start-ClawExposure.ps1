param(
    [int]$TTLHours = 2,
    [string]$AllowedIPs = ""
)

$ErrorActionPreference = "Stop"

if ($TTLHours -le 0) {
    throw "TTLHours must be > 0."
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $root "runtime"
$logsDir = Join-Path $runtimeDir "logs"
$composeFile = Join-Path $root "docker-compose.yml"
$caddyFile = Join-Path $runtimeDir "Caddyfile"
$sessionFile = Join-Path $runtimeDir "session.json"
$auditFile = Join-Path $logsDir "control_audit.log"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

# URL-safe one-time token
$token = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")).Substring(0, 48)
$startAt = Get-Date
$expireAt = $startAt.AddHours($TTLHours)

$ipList = @()
if (-not [string]::IsNullOrWhiteSpace($AllowedIPs)) {
    $ipList = $AllowedIPs.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

$ipBlock = ""
if ($ipList.Count -gt 0) {
    $ipJoined = ($ipList -join " ")
    $ipBlock = @"
    @ip_not_allowed not client_ip $ipJoined
    respond @ip_not_allowed "forbidden" 403
"@
}

$caddyContent = @"
:18070 {
$ipBlock
    @has_session_cookie header_regexp claw_session Cookie "(^|;\s*)claw_session=$token(;|$)"
    @valid_token query token=$token

    handle @has_session_cookie {
        @ws path /websocket*
        @longpoll path /longpolling/*
        reverse_proxy @ws host.docker.internal:8072 host.docker.internal:8070 {
            lb_policy first
        }
        reverse_proxy @longpoll host.docker.internal:8072 host.docker.internal:8070 {
            lb_policy first
        }
        reverse_proxy host.docker.internal:8070
    }

    handle @valid_token {
        # First pass with token: set short-lived session cookie for subsequent redirects/pages.
        header Set-Cookie "claw_session=$token; Path=/; HttpOnly; SameSite=Lax; Max-Age=$($TTLHours * 3600)"
        # Remove token before forwarding to Odoo.
        uri query -token
        @ws path /websocket*
        @longpoll path /longpolling/*
        reverse_proxy @ws host.docker.internal:8072 host.docker.internal:8070 {
            lb_policy first
        }
        reverse_proxy @longpoll host.docker.internal:8072 host.docker.internal:8070 {
            lb_policy first
        }
        reverse_proxy host.docker.internal:8070
    }

    respond "forbidden" 403

    log {
        output file /var/log/caddy/access.log
        format json
    }
}
"@

Set-Content -Path $caddyFile -Value $caddyContent -Encoding UTF8

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found."
}

docker compose -f $composeFile up -d --remove-orphans | Out-Null

$publicUrl = $null
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    $logs = docker compose -f $composeFile logs cloudflared --no-color 2>$null
    $m = [regex]::Match(($logs -join "`n"), "https://[a-z0-9-]+\.trycloudflare\.com")
    if ($m.Success) {
        $publicUrl = $m.Value
        break
    }
}

if (-not $publicUrl) {
    throw "Cloudflared tunnel URL was not found. Check: docker compose -f `"$composeFile`" logs cloudflared"
}

$session = [ordered]@{
    started_at = $startAt.ToString("s")
    expires_at = $expireAt.ToString("s")
    ttl_hours = $TTLHours
    token = $token
    allowed_ips = $ipList
    public_url = $publicUrl
    protected_url = "$publicUrl/?token=$token"
}
$session | ConvertTo-Json -Depth 5 | Set-Content -Path $sessionFile -Encoding UTF8

"$(Get-Date -Format s) START ttl_hours=$TTLHours url=$publicUrl allowed_ips=$AllowedIPs" | Add-Content -Path $auditFile -Encoding UTF8

$delayMinutes = [Math]::Max(1, $TTLHours * 60)
$stopScript = Join-Path $root "Stop-ClawExposure.ps1"
Start-Process -WindowStyle Hidden powershell -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$stopScript`"",
    "-DelayMinutes", "$delayMinutes",
    "-Reason", "ttl_auto_stop"
) | Out-Null

Write-Host ""
Write-Host "Claw temporary gateway is ready."
Write-Host "Public URL     : $publicUrl"
Write-Host "Protected URL  : $publicUrl/?token=$token"
Write-Host "Expires At     : $($expireAt.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "Audit Log      : $auditFile"
Write-Host ""
Write-Host "Use the protected URL in MiniMax Claw session."
