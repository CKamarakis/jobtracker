<#
.SYNOPSIS
  Bring up the whole Job-Hunt dev stack (Postgres -> API -> Vite) and print URLs.

.DESCRIPTION
  One idempotent command for all three tiers. An already-running tier is detected and
  reused, never double-started -- so repeated runs don't spawn orphan Vite servers
  (that's what caused the 5173->5174->5175 port creep).

  Order matters: Postgres is the API's data store, so it comes up first. Each tier is
  delegated to the script that owns it and is idempotent: db/pg.ps1 (PG) and
  api/serve.ps1 (API). Only the Vite tier is handled inline (PID file + log poll).

  IMPORTANT -- WHY THERE IS NO $ErrorActionPreference='Stop' HERE:
    Native exes (pg_ctl) write harmless warnings to stderr. Under 'Stop', PowerShell
    turns native stderr into a TERMINATING error -- which previously killed this script
    at the PG step, so API+Vite SILENTLY never started. Each tier now reports its own
    status; one tier's stderr must never abort the whole stack.

  Fallback if Windows file-locking keeps biting Postgres: docker-compose (see db/pg.ps1).

.EXAMPLE
  ./up.ps1            # start everything, reuse whatever's already up
  ./up.ps1 -Reload    # API auto-restarts on code edits
#>
[CmdletBinding()]
param([switch]$Reload)

$Root = $PSScriptRoot   # default ErrorActionPreference (Continue) on purpose -- see header

# --- 1. Postgres (:5433) -- db/pg.ps1 owns it, is idempotent, prints its own line ---
& (Join-Path $Root 'db\pg.ps1') start

# --- 2. API (FastAPI, :8000) -- serve.ps1 is idempotent + already probes /health ----
$serveArgs = @('start'); if ($Reload) { $serveArgs += '-Reload' }
& (Join-Path $Root 'api\serve.ps1') @serveArgs 6>$null   # 6>: mute its Write-Host, we print our own
# Don't trust exit codes -- probe /health so we never claim "ready" on a dead API.
$apiOk = $false
try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3 | Out-Null; $apiOk = $true } catch {}
if ($apiOk) { Write-Host 'API       ready    http://127.0.0.1:8000  (docs at /docs)' -ForegroundColor Cyan }
else        { Write-Host 'API       FAILED   -- see api\serve.ps1 status / port 8000 in use?' -ForegroundColor Red }

# --- 3. Web (Vite) -----------------------------------------------------------
$WebDir = Join-Path $Root 'web'
$WebPid = Join-Path $WebDir '.dev.pid'
$WebLog = Join-Path $WebDir '.dev.log'
$Node   = 'C:\Program Files\nodejs\node.exe'
$Vite   = Join-Path $WebDir 'node_modules\vite\bin\vite.js'

function Get-WebProc {
  if (-not (Test-Path $WebPid)) { return $null }
  $wpid = (Get-Content $WebPid | Select-Object -First 1).Trim()
  $p = Get-Process -Id $wpid -ErrorAction SilentlyContinue
  if ($p) { return $p }
  Remove-Item $WebPid -ErrorAction SilentlyContinue   # stale -> clean up
  return $null
}

$web = Get-WebProc
if (-not $web) {
  $proc = Start-Process -FilePath $Node -ArgumentList $Vite `
            -WorkingDirectory $WebDir -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $WebLog -RedirectStandardError (Join-Path $WebDir '.dev.err.log')
  $proc.Id | Out-File -FilePath $WebPid -Encoding ascii
  $web = $proc
}

# Poll the log for the URL Vite actually bound (it picks the next free port).
# Vite colorizes the port with ANSI escapes, so strip those before matching.
$webUrl = $null
foreach ($i in 1..20) {
  if (Test-Path $WebLog) {
    $raw = (Get-Content $WebLog -Raw) -replace "\x1b\[[0-9;]*m", ''
    $m = [regex]::Match($raw, 'http://localhost:\d+')
    if ($m.Success) { $webUrl = $m.Value; break }
  }
  if ($web.HasExited) { break }
  Start-Sleep -Milliseconds 400
}
if ($webUrl) {
  Write-Host "Web       ready    $webUrl" -ForegroundColor Green
} else {
  Write-Host "Web       started (PID $($web.Id)) -- URL not detected yet; see web\.dev.log" -ForegroundColor Yellow
}
