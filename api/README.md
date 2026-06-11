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
| GET | `/jobs` | `JobSummary[]` | Filters: `?status=` (`new\|shortlisted\|applied\|skipped`), `?verdict=` (`strong fit\|fit\|stretch\|reject`). Sorted strongest verdict first. No description. |
| GET | `/jobs/{id}` | `JobDetail` | Full record incl. `description`, triage trail. 404 if unknown. |
| GET | `/profile` | `string[]` | Slugs: `cv`, `criteria`, `experience-map`, `parameters`, `cover-template`. |
| GET | `/profile/{name}` | `MarkdownDoc` | Raw markdown. 404 if unknown. |
| GET | `/dossiers` | `string[]` | Company-dossier slugs. |
| GET | `/dossiers/{slug}` | `MarkdownDoc` | Raw markdown. 404 if unknown. |
| GET | `/cover-letters` | `string[]` | Cover-letter slugs. |
| GET | `/cover-letters/{slug}` | `MarkdownDoc` | Raw markdown. 404 if unknown. |

## Models (`api/models.py`)

- **`JobSummary`** — list-view shape: `id, source[], company, title, location, remote,
  url, ats_url, posted_date, status, triage_verdict`. No `description` (keeps list payloads small).
- **`JobDetail`** — `JobSummary` + `description, triaged_date, skip_reason, alt_locations`.
- **`MarkdownDoc`** — `{slug, markdown}` for any profile / dossier / cover-letter file.

`from_record()` on the job models is the single mapping from a raw pipeline record to
the API shape — the one place to touch when column names change in Phase D.

## Architecture notes

- **`api/data_source.py` is the seam.** Routes never `open()` a file or know a path;
  they call functions here. Phase D rewrites these function bodies to hit Postgres and
  the rest of the codebase (routes, models, React) is untouched. This is the
  "files now, DB later" bet from `ROADMAP.md`.
- **Read-only by design.** Phase B serves; it does not mutate. Writes (shortlist, notes,
  applied-dates) arrive with the DB in Phase D as new functions behind the seam.
- **CORS** is pre-opened for the local React dev ports (Vite `5173`, CRA `3000`).
  Tighten to the real origin at deploy time (Phase F).
- **Import quirk:** `ingest/` isn't an installed package, so the seam does a deliberate
  `sys.path.insert` to reuse `ingest/store.py`'s loader. Remove once the repo is packaged.

## TODO / next

- [ ] Phase C: React + MUI frontend consuming these endpoints.
- [ ] Phase D: swap `data_source.py` to Postgres; add write endpoints (shortlist, notes, status).
- [ ] Phase F: auth, tighten CORS, host.
