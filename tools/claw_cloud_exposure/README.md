# MiniMax Claw Cloud Exposure (Temporary)

This toolkit exposes local Odoo (`http://localhost:8070`) to a temporary HTTPS URL for cloud browser agents.

It provides:
- reverse proxy in front of Odoo (`caddy`)
- temporary public HTTPS tunnel (`cloudflared quick tunnel`)
- one-time token gate (`?token=...`)
- optional IP allowlist
- TTL auto-stop
- audit logs

## Prerequisites

- Docker Desktop running
- Docker CLI available in PowerShell
- Local Odoo reachable at `http://localhost:8070`

## Quick start

```powershell
cd E:\whm_Odoo_project\tools\claw_cloud_exposure
.\Start-ClawExposure.ps1 -TTLHours 2 -AllowedIPs "1.2.3.4,5.6.7.8"
```

If you do not want IP allowlist:

```powershell
.\Start-ClawExposure.ps1 -TTLHours 2
```

Output includes:
- `Public URL`
- `Protected URL` (append token automatically)
- expiration timestamp

Use `Protected URL` in your MiniMax Claw session.

## Stop immediately

```powershell
.\Stop-ClawExposure.ps1 -Reason manual
```

## Audit and logs

```powershell
.\Get-ClawExposureAudit.ps1 -Tail 200
```

Artifacts are in:
- `runtime/session.json`
- `runtime/logs/control_audit.log`
- `runtime/logs/access.log`

## MiniMax Claw policy template

Use:

- `minimax_claw_session_policy.example.json`

Replace:
- `REPLACE_WITH_PROTECTED_URL`
- `REPLACE_WITH_TRYCLOUDFLARE_HOST`

## Security notes

- Keep TTL short.
- Use test account credentials.
- Prefer setting `-AllowedIPs`.
- Stop exposure immediately after debugging.
- Token is passed via query string by default; treat session URL as sensitive.
