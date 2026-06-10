# py.ps1 - always-works Python launcher for this repo.
# Why: `python`/`py` intermittently are not on PATH (stale live-session PATH; see
# memory/project_python_env.md). This wrapper hard-codes the known-good interpreter
# and forces UTF-8 so German job text does not throw cp1252 UnicodeEncodeError.
# Usage:  ./py.ps1 ingest/run.py        ./py.ps1 -m pytest tests -q
$ErrorActionPreference = "Stop"
$Interp = "C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe"
if (-not (Test-Path $Interp)) {
    Write-Error "Interpreter not at $Interp - Python was moved/upgraded. Update py.ps1 + CLAUDE.md + memory once, then never search again."
    exit 1
}
$env:PYTHONUTF8 = "1"
& $Interp @args
exit $LASTEXITCODE
