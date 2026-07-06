<#
.SYNOPSIS
  Stop the Job-Hunt dev stack (Vite -> API -> Postgres).

.DESCRIPTION
  Reverse of up.ps1. Stops the Vite dev server (via its PID file), the API
  (via serve.ps1), and Postgres. Symmetric with up.ps1: it starts all three, so
  down stops all three. Stopping PG loses no data (rows live on disk in the data
  dir; stop just parks the listener). Pass -KeepPostgres to leave it warm.

.EXAMPLE
  ./down.ps1                 # stop everything
  ./down.ps1 -KeepPostgres   # stop web + API, leave Postgres running
#>
[CmdletBinding()]
param([switch]$KeepPostgres)

# Default (Continue) on purpose: a native-exe stderr warning during teardown must not
# abort the script and leave a tier half-stopped. Mirror of up.ps1's header rationale.
$Root = $PSScriptRoot

# --- Web ---------------------------------------------------------------------
$WebPid = Join-Path $Root 'web\.dev.pid'
if (Test-Path $WebPid) {
  $wpid = (Get-Content $WebPid | Select-Object -First 1).Trim()
  $p = Get-Process -Id $wpid -ErrorAction SilentlyContinue
  if ($p) { Stop-Process -Id $wpid -Force; Write-Host "Web       stopped (PID $wpid)" -ForegroundColor Green }
  else    { Write-Host 'Web       not running' -ForegroundColor Yellow }
  Remove-Item $WebPid -ErrorAction SilentlyContinue
} else {
  Write-Host 'Web       not running' -ForegroundColor Yellow
}

# --- API ---------------------------------------------------------------------
& (Join-Path $Root 'api\serve.ps1') stop 6>$null
Write-Host 'API       stopped' -ForegroundColor Green

# --- Postgres ----------------------------------------------------------------
if ($KeepPostgres) {
  Write-Host 'Postgres  left running (:5433) -- -KeepPostgres set' -ForegroundColor Yellow
} else {
  & (Join-Path $Root 'db\pg.ps1') stop 6>$null
  Write-Host 'Postgres  stopped' -ForegroundColor Green
}
