# HANDOFF — 2026-06-11 (Phase B FastAPI shipped; next = Phase C React)

Transient note for the next session. Full rationale persisted in memory:
`project_state_2026-06-11.md` (+ `project_app_roadmap.md` for the phased plan).

## Where we are (good state — nothing broken)
- **PIVOTED from pipeline tuning to building the app.** Chris's steer: enough
  evals/ingest for now — build app functionality. Don't re-offer eval/fetch work
  unless he asks.
- **Phase B SHIPPED & MERGED** (PR #5, commit `24b5001` on `main`; local synced).
  Read-only FastAPI over the existing pipeline artifacts. New `api/` package:
  - `api/data_source.py` = **THE SEAM**. Every route reads through it; nothing
    touches a file path directly. Phase D swaps this ONE module to Postgres and the
    rest is untouched. Reuses `ingest/store.load_jobs`.
  - `api/models.py` = Pydantic `JobSummary`/`JobDetail`/`MarkdownDoc`; `from_record()`
    is the single record→API mapping.
  - `api/main.py` = thin routes + CORS pre-opened for Vite 5173 / CRA 3000.
  - Endpoints: `/health`, `/jobs?status=&verdict=` (strongest-first), `/jobs/{id}`,
    `/profile[/{name}]`, `/dossiers[/{slug}]`, `/cover-letters[/{slug}]`.
  - `api/serve.ps1` = start/stop/restart/open/status (PID-file + post-start `/health`
    poll, fails loudly on bad port bind). `.server.pid` gitignored.
  - `api/README.md` = **LIVING docs** — keep updated as the API changes.
- **Pool:** 193 jobs in `data/jobs.jsonl`, triaged (3 strong / 2 fit / 5 stretch /
  152 reject / 31 untriaged), 5 shortlisted. From ~06-10; NOT re-fetched on purpose.

## Run the API
```powershell
./api/serve.ps1 start    # then: ./api/serve.ps1 open  → http://127.0.0.1:8000/docs
./api/serve.ps1 status   # running? + live /health
./api/serve.ps1 stop
```
Manual: `$env:PYTHONUTF8=1; & <py> -m uvicorn api.main:app --reload`.

## DO THIS NEXT — Phase C (React + MUI frontend)
Build the UI that consumes the Phase B endpoints (ROADMAP.md Phase C):
list (filter by verdict/status, strongest first) → detail page → client-side
routing → select → **transient** shortlist (no DB yet — that's Phase D). React may
be newer ground; teach the component/hooks/routing/MUI choices as we go.
Make sure the API is up (`./api/serve.ps1 status`) so the frontend has a target.

## Gotcha learned this session
An orphan uvicorn from a "stopped" background task kept squatting port 8000 → the
new server couldn't bind and died, but a naive start would report success. Fix =
PID file + post-start health poll (now baked into `serve.ps1`).

## Env
Python: `C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe` (full
path — PATH is session-mangled; fastapi+uvicorn installed here).
git → Bash tool. gh → `"/c/Program Files/GitHub CLI/gh.exe"` from Bash tool.
