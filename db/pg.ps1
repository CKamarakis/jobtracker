<#
.SYNOPSIS
  Start / stop / status / psql for the portable dev Postgres (Phase D).

.DESCRIPTION
  The DB is a portable EnterpriseDB binary build (no installer, no Windows service, no admin)
  living OUTSIDE the repo at $PgRoot, with its data dir at $PgData. It listens on port 5433
  (not 5432) so it never clashes with a system Postgres. This script is the one place to
  control it — mirrors api/serve.ps1 for the API.

  Connection string (matches db/engine.py's default):
    postgresql+psycopg://jobhunt:jobhunt@localhost:5433/jobhunt

.EXAMPLE
  ./db/pg.ps1 start        # start the cluster
  ./db/pg.ps1 status       # is it up?
  ./db/pg.ps1 psql         # open an interactive psql shell on the jobhunt db
  ./db/pg.ps1 stop
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'restart', 'status', 'psql')]
  [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'

$PgRoot = 'C:\Users\Chris\pgportable'
$Bin    = Join-Path $PgRoot 'pgsql\bin'
$PgData = Join-Path $PgRoot 'data'
$Port   = 5433
$env:PGPASSWORD = 'jobhunt'

function Pg-Status {
  & "$Bin\pg_ctl.exe" -D $PgData status
}

switch ($Action) {
  'start'   { & "$Bin\pg_ctl.exe" -D $PgData -o "-p $Port" -l (Join-Path $PgData 'server.log') start }
  'stop'    { & "$Bin\pg_ctl.exe" -D $PgData stop -m fast }
  'restart' { & "$Bin\pg_ctl.exe" -D $PgData -o "-p $Port" -l (Join-Path $PgData 'server.log') restart }
  'status'  { Pg-Status }
  'psql'    { & "$Bin\psql.exe" -U jobhunt -h localhost -p $Port -d jobhunt }
}
