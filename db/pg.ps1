<#
.SYNOPSIS
  Start / stop / status / restart / psql for the portable dev Postgres (Phase D).

.DESCRIPTION
  Portable EnterpriseDB build (no installer, no Windows service, no admin) at $PgRoot,
  data dir $PgData, listening on :5433 (so it never clashes with a system Postgres).
  This is the ONE place that controls the cluster.

  Hardened against three Windows gotchas that used to make startup slow and dishonest:
   1. LOG LIVES OUTSIDE THE DATA DIR ($PgRoot\pg.log). PG's startup fsync walks the
      WHOLE data dir; a server.log inside it collides with pg_ctl's own -l writer and
      stalls ~27s on a Windows "sharing violation". Keeping the log out avoids that.
   2. pg_isready is the SOURCE OF TRUTH for "is it up?", not `pg_ctl status` + a pid
      file (which lies after an unclean shutdown / stale postmaster.pid).
   3. Native-exe stderr is NOT allowed to abort the script (no ErrorActionPreference
      ='Stop' around pg_ctl; streams muted with *>$null). A harmless pg_ctl warning
      to stderr previously became a terminating error and killed the caller.

  A crash/kill (no clean stop) forces a full data-dir fsync + WAL recovery on the next
  start (~34s). ALWAYS stop cleanly (down.ps1 / this script's `stop`) to keep starts ~3s.

  If Windows file-locking keeps biting despite the above, the documented fallback is
  docker-compose (postgres:16 with a healthcheck + named volume) -- see up.ps1 header.

  Connection string (matches db/engine.py's default):
    postgresql+psycopg://jobhunt:jobhunt@localhost:5433/jobhunt

.EXAMPLE
  ./db/pg.ps1 start        # start the cluster (reused if already up)
  ./db/pg.ps1 status       # is it accepting connections?
  ./db/pg.ps1 psql         # interactive psql shell on the jobhunt db
  ./db/pg.ps1 stop
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'restart', 'status', 'psql')]
  [string]$Action = 'status'
)

# NOTE: deliberately NOT 'Stop'. pg_ctl writes benign warnings to stderr; under 'Stop'
# PowerShell would turn those into terminating errors and abort the caller (up.ps1).
$ErrorActionPreference = 'Continue'

$PgRoot = 'C:\Users\Chris\pgportable'
$Bin    = Join-Path $PgRoot 'pgsql\bin'
$PgData = Join-Path $PgRoot 'data'
$Log    = Join-Path $PgRoot 'pg.log'   # OUTSIDE $PgData on purpose (see header, gotcha #1)
$Port   = 5433
$env:PGPASSWORD = 'jobhunt'

function Test-PgReady {
  # The one honest "is it up?" check: pg_isready exits 0 only when accepting connections.
  & "$Bin\pg_isready.exe" -h localhost -p $Port -q *> $null
  return ($LASTEXITCODE -eq 0)
}

function Start-Pg {
  if (Test-PgReady) { Write-Host "Postgres  reused   :$Port" -ForegroundColor Yellow; return }
  # -w -t 60: wait (up to 60s) for readiness so we never claim "started" on a dead cluster;
  # the 60s headroom covers a crash-recovery fsync after an unclean prior shutdown.
  & "$Bin\pg_ctl.exe" -D $PgData -o "-p $Port" -l $Log -w -t 60 start *> $null
  if (Test-PgReady) { Write-Host "Postgres  started  :$Port" -ForegroundColor Green }
  else              { Write-Host "Postgres  FAILED   -- see $Log" -ForegroundColor Red }
}

function Stop-Pg {
  if (-not (Test-PgReady)) { Write-Host 'Postgres  not running' -ForegroundColor Yellow; return }
  & "$Bin\pg_ctl.exe" -D $PgData -m fast -w -t 60 stop *> $null
  if (Test-PgReady) { Write-Host 'Postgres  STOP FAILED -- still accepting connections' -ForegroundColor Red }
  else              { Write-Host 'Postgres  stopped' -ForegroundColor Green }
}

switch ($Action) {
  'start'   { Start-Pg }
  'stop'    { Stop-Pg }
  'restart' { Stop-Pg; Start-Pg }
  'status'  {
    if (Test-PgReady) { Write-Host "Postgres  up       :$Port" -ForegroundColor Green }
    else              { Write-Host 'Postgres  down' -ForegroundColor Yellow }
  }
  'psql'    { & "$Bin\psql.exe" -U jobhunt -h localhost -p $Port -d jobhunt }
}
