# HANDOFF — 2026-06-17 (Phase D BUILT on `phase-d-postgres`; next = review + merge)

Transient note for the next session. **Authoritative docs:** `CLAUDE.md` (operating manual),
`ROADMAP.md` (phase history + the Phase D "SHIPPED" summary), `docs/ENV.md` (tooling + the new
Postgres setup — don't search for binaries).

## State / housekeeping
- **On branch `phase-d-postgres`** (off `main` @ `0470ac8`). **Not committed yet** — Chris
  reviews first. Working tree has all Phase D changes (see below).
- **Postgres is running** (portable build, port 5433). Control: `./db/pg.ps1 start|stop|status|psql`.
  If a fresh session finds it down, `./db/pg.ps1 start`. Connection string is db/engine.py's
  default; no `DATABASE_URL` needed for local.
- **A stale uvicorn from an earlier session may be on :8000** (it runs OLD file-based code and
  will 405 on `PATCH /jobs`). Kill it before testing:
  `Get-NetTCPConnection -LocalPort 8000 -State Listen | % { Stop-Process -Id $_.OwningProcess -Force }`,
  then `./api/serve.ps1 start`.

## What Phase D shipped (all 8 build-order steps + acceptance test — see ROADMAP)
- **`db/` package** = persistence engine: `engine.py`, `models.py` (3 tables), `repository.py`,
  `seed.py`, `pg.ps1`. Imports no web stack, so `ingest` and `api` both use it (no circular dep).
- **Alembic** at repo root (`alembic.ini`, `alembic/`); migration `0001_initial` creates the
  split schema (`jobs` / `job_actions` / `application_notes`). Apply: `<py> -m alembic upgrade head`.
- **Seam swap proven:** `api/data_source.py` job fns delegate to `db.repository`; `api/main.py`
  reads, `api/models.py`, and the React app needed ~zero changes (only added `PATCH /jobs/{id}`,
  the `?window=N` dashboard param, and a `notes` summary field).
- **Durable pool:** `ingest/run.py` upserts (never wipes). Verified: re-upserting the 227-job pool
  kept count at 227, kept a shortlisted job shortlisted, bumped `last_seen_at`, left `first_seen_at`.
- **Persistence:** React notes/remove/approve now PATCH and survive a refresh (the acceptance test).
- **Store:** portable Postgres (EnterpriseDB binary, no installer/service/Docker; Docker → G6).
- Tests green (97 passed). Frontend builds clean.

## DO THIS NEXT
1. **Chris eyeballs the running app** end-to-end: `./db/pg.ps1 start`; `./api/serve.ps1 start`;
   `cd web; npm run dev`. Go-fetch → approve/note a job → refresh → it persists.
2. **Commit + PR** once Chris green-lights (don't commit unprompted). Branch: `phase-d-postgres`.
3. **Deferred / backlog:** `application_notes` endpoints (table + repo fns exist; routes are G4),
   Docker-compose for PG (G6), `data/jobs.jsonl` is now just the seed source (not live).

## Env
- Python: `C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe` (UTF-8) or `./py.ps1`.
- git → Bash tool. gh → `"/c/Program Files/GitHub CLI/gh.exe"` from Bash tool.
- Node at `C:\Program Files\nodejs`. `web/` = Vite + React + TS + Tailwind v4 + shadcn → :5173.
- Postgres: portable build at `C:\Users\Chris\pgportable`, port 5433. See `docs/ENV.md`.
