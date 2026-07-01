<#
.SYNOPSIS
  Bring up the whole Job-Hunt dev stack (Postgres -> API -> Vite) and print URLs.

.DESCRIPTION
  One command for all three tiers. Every step is IDEMPOTENT: an already-running
  tier is detected and reused, never double-started -- so repeated runs don't
  spawn orphan Vite servers (that's what caused the 5173->5174->5175 port creep).

  Order matters: Postgres is the API's data store on this branch, so it comes up
  first. Delegates to db/pg.ps1 + api/serve.ps1 where they already do the job;
  only the web tier is handled inline (a PID file + log poll, mirroring serve.ps1).

.EXAMPLE
  ./up.ps1            # start everything, reuse whatever's already up
  ./up.ps1 -Reload    # API auto-restarts on code edits
#>
[CmdletBinding()]
param([switch]$Reload)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

# --- 1. Postgres (portable, :5433) -------------------------------------------
$PgBin  = 'C:\Users\Chris\pgportable\pgsql\bin'
$PgData = 'C:\Users\Chris\pgportable\data'
& "$PgBin\pg_ctl.exe" -D $PgData status *> $null
if ($LASTEXITCODE -eq 0) {
  Write-Host 'Postgres  reused   :5433' -ForegroundColor Yellow
} else {
  & "$PgBin\pg_ctl.exe" -D $PgData -o '-p 5433' -l (Join-Path $PgData 'server.log') start *> $null
  Write-Host 'Postgres  started  :5433' -ForegroundColor Green
}

# --- 2. API (FastAPI, :8000) -- serve.ps1 is already idempotent --------------
$serveArgs = @('start'); if ($Reload) { $serveArgs += '-Reload' }
& (Join-Path $Root 'api\serve.ps1') @serveArgs 6>$null   # 6>: mute its Write-Host
# Don't trust the exit -- probe /health so we never claim "ready" on a dead API.
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
# Vite colorizes the port with ANSI escapes (http://localhost:<ESC>5173), so
# strip those before matching or the digits hide behind an escape sequence.
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
