<#
.SYNOPSIS
  Start / stop / open the Job-Hunt API (FastAPI + uvicorn).

.DESCRIPTION
  One place to manage the dev server so you never hunt for a stray python process.
  The running server's PID is recorded in api/.server.pid; stop/status/restart read
  it from there. See api/README.md for the endpoint reference.

.EXAMPLE
  ./api/serve.ps1 start          # background, port 8000
  ./api/serve.ps1 start -Reload  # auto-restart on code edits
  ./api/serve.ps1 open           # open Swagger UI in the browser
  ./api/serve.ps1 status         # running? + live /health
  ./api/serve.ps1 stop
  ./api/serve.ps1 restart
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'restart', 'open', 'status')]
  [string]$Action = 'start',

  [int]$Port = 8000,
  [switch]$Reload
)

$ErrorActionPreference = 'Stop'

# Repo root = parent of this api/ dir. Paths derive from it so the script works from anywhere.
$Root    = Split-Path -Parent $PSScriptRoot
$Python  = 'C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe'
$PidFile = Join-Path $PSScriptRoot '.server.pid'
$DocsUrl = "http://127.0.0.1:$Port/docs"

function Get-ServerProc {
  # Returns the live uvicorn process if the PID file points at one, else $null
  # (and clears a stale PID file).
  if (-not (Test-Path $PidFile)) { return $null }
  $recordedPid = (Get-Content $PidFile | Select-Object -First 1).Trim()
  $proc = Get-Process -Id $recordedPid -ErrorAction SilentlyContinue
  if ($proc) { return $proc }
  Remove-Item $PidFile -ErrorAction SilentlyContinue   # stale → clean up
  return $null
}

function Start-Server {
  $existing = Get-ServerProc
  if ($existing) {
    Write-Host "Already running (PID $($existing.Id)) -> $DocsUrl" -ForegroundColor Yellow
    return
  }
  $uargs = @('-m', 'uvicorn', 'api.main:app', '--port', "$Port")
  if ($Reload) { $uargs += '--reload' }

  # PYTHONUTF8 avoids cp1252 errors on German job text. Start-Process inherits this env.
  $env:PYTHONUTF8 = '1'
  $proc = Start-Process -FilePath $Python -ArgumentList $uargs `
            -WorkingDirectory $Root -PassThru -WindowStyle Hidden
  $proc.Id | Out-File -FilePath $PidFile -Encoding ascii

  # Confirm it actually came up — a failed port bind (port already in use) makes uvicorn
  # exit within ~1s, so a naive "Started" message would be a lie. Poll /health briefly.
  $up = $false
  foreach ($i in 1..10) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) { break }
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 | Out-Null; $up = $true; break } catch {}
  }
  if (-not $up) {
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Host "FAILED to start on port $Port (port in use? check with: Get-NetTCPConnection -LocalPort $Port)." -ForegroundColor Red
    return
  }
  Write-Host "Started (PID $($proc.Id)) on port $Port." -ForegroundColor Green
  Write-Host "Docs: $DocsUrl   (./api/serve.ps1 open)" -ForegroundColor Cyan
}

function Stop-Server {
  $proc = Get-ServerProc
  if (-not $proc) { Write-Host 'Not running.' -ForegroundColor Yellow; return }
  Stop-Process -Id $proc.Id -Force
  Remove-Item $PidFile -ErrorAction SilentlyContinue
  Write-Host "Stopped (PID $($proc.Id))." -ForegroundColor Green
}

function Show-Status {
  $proc = Get-ServerProc
  if (-not $proc) { Write-Host 'Server: NOT running.' -ForegroundColor Yellow; return }
  Write-Host "Server: running (PID $($proc.Id)), port $Port." -ForegroundColor Green
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
    Write-Host "Health: $($health.status), jobs=$($health.jobs)" -ForegroundColor Cyan
  } catch {
    Write-Host 'Health: process up but /health did not answer yet.' -ForegroundColor Yellow
  }
}

function Open-Docs {
  if (-not (Get-ServerProc)) { Write-Host 'Server not running - starting it first...' -ForegroundColor Yellow; Start-Server }
  Start-Process $DocsUrl   # default browser
  Write-Host "Opening $DocsUrl" -ForegroundColor Cyan
}

switch ($Action) {
  'start'   { Start-Server }
  'stop'    { Stop-Server }
  'restart' { Stop-Server; Start-Server }
  'open'    { Open-Docs }
  'status'  { Show-Status }
}
