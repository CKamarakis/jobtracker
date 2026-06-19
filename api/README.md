# Job-Hunt API — Phase B

Living documentation for the API layer. **Update this file as the API changes** —
new endpoints, new models, the Postgres swap in Phase D, auth in Phase F.

- **Status:** Phase B complete — read-only API over the pipeline artifacts. Built 2026-06-11.
- **Stack:** FastAPI + uvicorn (Python 3.14). Pydantic response models.
- **Backing store:** local files today (`data/jobs.jsonl`, `profile/*.md`, dossiers,
  cover letters), all read through one seam (`api/data_source.py`). Postgres replaces
  that seam in Phase D; nothing else changes.

## Run it

**Via the control script (recommended)** — from repo root:

```powershell
./api/serve.ps1 start     # launch the server in the background (port 8000)
./api/serve.ps1 open      # open the interactive docs in your browser
./api/serve.ps1 status    # is it running? + live /health
./api/serve.ps1 stop      # shut it down
./api/serve.ps1 restart   # stop + start (use after code changes if not using --reload)
```

`start` accepts `-Port` and `-Reload`:
```powershell
./api/serve.ps1 start -Port 8001 -Reload   # auto-restart on code edits
```

**Manual (no script)** — from repo root:
```powershell
$env:PYTHONUTF8=1
& "C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe" -m uvicorn api.main:app --reload
```

## Interactive docs (Swagger UI)

Once running: **http://127.0.0.1:8000/docs**

FastAPI auto-generates this from the Pydantic models — it's always current, and you
can fire requests at every endpoint from the page. Raw OpenAPI JSON at `/openapi.json`
(this is what the React frontend will generate its client against in Phase C).

## Endpoints

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/health` | `{status, jobs}` | Liveness + job count; the smoke test. |
| GET | `/jobs` | `JobSummary[]` | Filters: `?status=` (`new\|shortlisted\|applied\|skipped`), `?verdict=` (`strong fit\|fit\|stretch\|reject`). `?window=N` → dashboard VIEW (jobs posted within N days OR human-touched; durable-pool filter). Sorted strongest verdict first. No description. |
| GET | `/jobs/{id}` | `JobDetail` | Full record incl. `description`, triage trail. 404 if unknown. |
| PATCH | `/jobs/{id}` | `JobDetail` | **WRITE (Phase D).** Body `{status?, notes?, applied_date?}`; persists a review action to `job_actions`. 400 on bad status, 404 if unknown. Makes notes/remove/approve survive a refresh. |
| GET | `/profile` | `string[]` | Slugs: `cv`, `criteria`, `experience-map`, `parameters`, `cover-template`. |
| GET | `/profile/{name}` | `MarkdownDoc` | Raw markdown. 404 if unknown. |
| GET | `/dossiers` | `string[]` | Company-dossier slugs. |
| GET | `/dossiers/{slug}` | `MarkdownDoc` | Raw markdown. 404 if unknown. |
| GET | `/cover-letters` | `string[]` | Cover-letter slugs. |
| GET | `/cover-letters/{slug}` | `MarkdownDoc` | Raw markdown. 404 if unknown. |

## Models (`api/models.py`)

- **`JobSummary`** — list-view shape: `id, source[], company, title, location, remote,
  url, ats_url, posted_date, status, triage_verdict, triage_reason, notes`. No `description`.
- **`JobDetail`** — `JobSummary` + `description, triaged_date, skip_reason, alt_locations`.
- **`MarkdownDoc`** — `{slug, markdown}` for any profile / dossier / cover-letter file.

`from_record()` on the job models is the single mapping from a raw record to the API shape.
**Phase D made this concrete:** the store moved to Postgres but the record dict crossing
`data_source` keeps the same keys, so `from_record` — and the React app — were untouched.

## Architecture notes

- **`api/data_source.py` is the seam.** Routes never `open()` a file or know a path;
  they call functions here. **Phase D rewrote the job function BODIES to hit Postgres**
  (via the `db/` package) and the rest of the codebase (routes, models, React) was untouched
  — the "files now, DB later" bet from `ROADMAP.md`, delivered.
- **Now read + write.** `PATCH /jobs/{id}` → `data_source.patch_job_action` → `db.repository`,
  persisting status/notes/applied-date to the `job_actions` table. Markdown docs stay on disk.
- **CORS** is pre-opened for the local React dev ports (Vite `5173`, CRA `3000`).
  Tighten to the real origin at deploy time (Phase F).
- **Persistence engine = `db/`** (engine/models/repository/seed). It imports no web stack so
  `ingest/run.py` can upsert through the same repository without dragging FastAPI in.

## TODO / next

- [x] Phase C: React frontend consuming these endpoints (Tailwind + shadcn, not MUI).
- [x] Phase D: swapped `data_source.py` to Postgres; `PATCH /jobs/{id}` write endpoint live.
- [ ] G4: `application_notes` endpoints (table + repo fns already exist).
- [ ] Phase F: auth, tighten CORS, host.
