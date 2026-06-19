# Phase D — Postgres behind the seam (implementation plan)

**Status:** ✅ BUILT 2026-06-17 on branch `phase-d-postgres` (all 8 build-order steps + the
acceptance test). See `ROADMAP.md` → "Phase D — SHIPPED" for the what-landed summary. This file
remains the build-level reference; the only deviations from spec: store is **portable Postgres**
(EnterpriseDB binary build, port 5433 — no installer/service, fully reversible) and a `notes`
field was added to the list summary so the note indicator survives a refresh too.

## Goal (one sentence)
Move the backing store from JSONL → **Postgres**, so the currently LOCAL-ONLY review actions
(status / notes / applied-date) survive a refresh — **without the React app or the API contract
noticing the swap**. That "swap the store behind a stable seam" is the whole learning point of D.

## Locked decisions (do NOT relitigate — settled with Chris)
1. **Postgres day one** (no SQLite-then-migrate). **Native install now; Docker deferred** → backlog G6.
2. **SQLAlchemy (ORM) + Alembic (migrations).**
3. **Split schema** — three tables (see below). Ingest data and human edits have opposite
   lifecycles, so they live apart.
4. **Pool is durable; the dashboard is a filtered VIEW, not a wipe.** Re-fetch **upserts**
   (dedup-merge), never truncates. Approved/applied jobs re-seen on the board **keep their status**.
5. **First WRITE endpoint:** `PATCH /jobs/{id}` (status, notes, applied-date).
6. `api/data_source.py` stays the API-facing seam. (New: a `db/` package is the actual
   persistence engine — see "Where the DB code lives".)

---

## Schema — three tables

### `jobs` — source-owned ad data (re-fetched, overwritten freely)
Mirrors today's JSONL record. Re-fetch upserts onto it; ingest may overwrite any column here
**except** the timestamps' insert-only semantics.

| column | type | notes |
|---|---|---|
| `id` | text PK | existing 16-char dedup hash (`ingest/store.job_key`) — keep it, don't switch to serial |
| `source` | text[] | union-merged across sources (jsonb also fine; array is closer to today) |
| `company` | text | |
| `title` | text | |
| `location` | text | |
| `alt_locations` | text[] null | distinct non-primary cities from a location-spanning collapse |
| `remote` | bool null | |
| `url` | text null | |
| `ats_url` | text null | |
| `description` | text null | keep the richer (longer) on merge — existing rule |
| `posted_date` | date null | the ad's own date; **primary axis for the 1d–1w freshness window** |
| `posted_ts` | bigint null | epoch mirror of posted_date; keep earliest on merge (existing rule) |
| `triage_verdict` | text null | strong fit \| fit \| stretch \| reject |
| `triage_reason` | text null | one-liner |
| `triaged_date` | text null | |
| `skip_reason` | text null | pre-filter drop reason |
| `first_seen_at` | timestamptz | **set on INSERT only, never updated** |
| `last_seen_at` | timestamptz | **bumped on every upsert** — "still live on the board" vs "fell off" |

> `status` does NOT live here. It moved to `job_actions` so a re-fetch upsert can never clobber it.

### `job_actions` — sacred human edits (ingest NEVER touches this table)
| column | type | notes |
|---|---|---|
| `job_id` | text PK / FK→jobs.id | one row per job, created lazily on first edit |
| `status` | text | `new \| shortlisted \| applied \| skipped`. Absence of a row ⇒ treat as `new`. |
| `notes` | text null | lightweight triage-time note (~1–2% of ads) |
| `applied_date` | date null | |
| `updated_at` | timestamptz | bumped on each PATCH |

> Modeling status here (not jobs) is what makes "durable pool + filtered dashboard" safe: the
> upsert writes only `jobs`; human status is in a table ingest has no reason to write.

### `application_notes` — only for jobs actually applied to
| column | type | notes |
|---|---|---|
| `job_id` | text PK / FK→jobs.id | one row per application |
| `notes` | text null | **seeded once** by copying `job_actions.notes` at create; no ongoing sync after |
| `salary` | text null | free-text range (e.g. "90–110k") |
| `links` | text[] null | extra links (portfolio, referral, posting variants) |
| `created_at` / `updated_at` | timestamptz | |

**The copy-once rule (Chris, explicit):** on `application_notes` row creation, copy the current
`job_actions.notes` into `application_notes.notes` **if the target is empty**; thereafter the two
fields diverge freely — do **not** keep them in sync.

---

## Where the DB code lives (resolve the seam/circular-import question)
Today `api/data_source.py` imports `ingest.store`. If ingest's run also needed to import
`api.data_source`, that's circular — and `ingest/run.py` must stay runnable standalone
(`./py.ps1 ingest/run.py`) without importing the web stack.

**Decision:** introduce a **`db/` package** as the persistence engine that BOTH callers use:
- `db/engine.py` — SQLAlchemy engine + session factory; reads `DATABASE_URL` from env
  (default `postgresql+psycopg://jobhunt:jobhunt@localhost:5432/jobhunt`).
- `db/models.py` — the three ORM classes above.
- `db/repository.py` — plain functions: `list_jobs(...)`, `get_job(id)`, `upsert_jobs(records)`,
  `patch_action(job_id, **fields)`, `get/create_application_notes(...)`, `dashboard_jobs(...)`.
- `api/data_source.py` keeps its current function signatures but its **bodies now delegate to
  `db.repository`** instead of reading JSONL. Routes/models/React unchanged. (That delegation
  IS the "swap behind the seam" deliverable — keep the diff to function bodies.)
- `ingest/run.py` calls `db.repository.upsert_jobs(...)` instead of `store.save_jobs(...)`.

> `db/` (not `api/`) so ingest can import it without dragging FastAPI in. Keeps the no-web-imports
> discipline `data_source.py`'s docstring already states.

---

## The upsert (replaces wipe-and-replace)
`ingest/run.py:85` currently does `jobs = {}` (fresh pool) → `store.save_jobs` (overwrite file).
Replace the persist step with an upsert that reuses the EXISTING merge semantics
(`ingest/store.merge_job` — richer description, union sources, earliest date, **status preserved**):

Per incoming record:
1. `SELECT` existing `jobs` row by `id`.
2. **New** → INSERT; set `first_seen_at = last_seen_at = now()`. No `job_actions` row yet (⇒ `new`).
3. **Existing** → apply `merge_job` rules to the ad columns, **bump `last_seen_at = now()`**,
   leave `first_seen_at` untouched. Never write `job_actions` from here.

Use PG `INSERT ... ON CONFLICT (id) DO UPDATE` for atomicity. `merge_job` already encodes the field
rules — port it, don't reinvent. **Do not truncate the table on fetch.**

---

## Dashboard = filtered view (the "durable + filter" call)
Stop physically removing old results. `repository.dashboard_jobs()` query:

```sql
SELECT ... FROM jobs LEFT JOIN job_actions USING (job_id-ish)
WHERE  posted_date >= (now() - :window)          -- 1d / 3d / 1w freshness knob
   OR  COALESCE(job_actions.status,'new') <> 'new'   -- anything the human has touched stays
ORDER BY <verdict strength>, company;
```
Effect: this run's fresh results **plus** every approved/applied/noted job, regardless of age.
Stale untouched `new` jobs simply don't render — same clean "last run" feel as wiping, but
applications/edits never disappear. `last_seen_at` is available if we later want "still live"
badges, but is NOT required for this query.

> `list_jobs()` (the existing `/jobs` endpoint) can keep returning the full set with optional
> filters; the **dashboard** uses the windowed query. Decide whether to add a `window` param to
> `/jobs` or a dedicated `/dashboard` endpoint — lean toward a `window` query param on `/jobs`
> to avoid a new route (smaller contract change).

---

## New / changed API surface
- **`PATCH /jobs/{id}`** — body `{status?, notes?, applied_date?}`. Upserts the `job_actions` row.
  Returns the updated `JobDetail` (now sourced from the join). 404 if `job_id` unknown in `jobs`.
- **Approve** action → `status='shortlisted'`. **Remove** → `status='skipped'` (soft; Chris wants
  data kept — never hard-delete). **Notes** → `job_actions.notes`.
- **`application_notes`** (can be a thin slice now, or G4 later — confirm scope with Chris):
  `POST /jobs/{id}/application` (create, seeds notes once), `PATCH /jobs/{id}/application`,
  `GET` folds into `JobDetail`. If time-boxed, ship `PATCH /jobs/{id}` first and defer
  `application_notes` endpoints to G4 — the table can exist before its endpoints do.
- `JobSummary`/`JobDetail.from_record` mapping (`api/models.py`) absorbs any column-name diff —
  that's exactly the indirection its docstring was built for. React stays untouched.

---

## Migrations (Alembic)
- `alembic init`, point `sqlalchemy.url` at `DATABASE_URL` (env, not hardcoded).
- **Migration 1:** create all three tables + indexes (`jobs.posted_date`, `job_actions.status`).
- Keep `target_metadata = db.models.Base.metadata` so autogenerate works.
- Learning note to write inline: autogenerate diffs models vs DB — always eyeball the generated
  script (it misses some constraint/enum changes); never blind-apply.

## Seeding the dev DB from the existing JSONL pool
- One-off `db/seed.py`: read `data/jobs.jsonl` via `ingest.store.load_jobs`, map each record →
  `jobs` row, set `first_seen_at = last_seen_at = now()`, carry any existing `status` into a
  `job_actions` row only if it's non-`new`. Idempotent (upsert), so it can re-run.
- This also doubles as the first real exercise of `upsert_jobs`.

## Dependencies / env
- Add `sqlalchemy`, `alembic`, `psycopg[binary]` to requirements (confirm the requirements file).
- **Native Postgres install** (no Docker): create role `jobhunt` / db `jobhunt`. Document the
  exact commands in `docs/ENV.md` (Chris's machine; Windows — likely the PG installer + `psql`).
- `DATABASE_URL` env var; never commit credentials. `.env` is already gitignored — verify.

---

## Build order (suggested, each a safe stopping point)
1. **Deps + native PG up**, `DATABASE_URL` wired, `db/engine.py` connects (smoke: `SELECT 1`).
2. **`db/models.py`** (3 tables) + **Alembic migration 1** applied. Inspect with `psql \d`.
3. **`db/repository.py` read functions** + delegate `data_source.list_jobs/get_job` to them.
   `/health` + `/jobs` + detail still green against an **empty** DB.
4. **`db/seed.py`** → load the JSONL pool. `/jobs` now serves from PG. Eyeball parity vs old file.
5. **`upsert_jobs`** + rewire `ingest/run.py` off `save_jobs`. Run a fetch; confirm it MERGES
   (count grows/holds, doesn't reset), `last_seen_at` bumps, statuses survive.
6. **`PATCH /jobs/{id}`** + `patch_action`. Wire the React review actions (notes/remove/approve)
   to it; confirm they **survive a refresh** (the whole point).
7. **Dashboard windowed query** swap. Confirm touched-jobs persist past the freshness window.
8. *(optional / G4)* `application_notes` endpoints + copy-once seed.

## Verification
- After step 6: approve a job → refresh browser → still approved. That's the acceptance test.
- Re-run a fetch after approving → the approved job stays `shortlisted`, isn't wiped, `last_seen_at`
  advanced. Run the existing eval set unaffected (triage path untouched).
- Keep all existing read endpoints returning the same JSON shape — diff `/jobs` output before/after
  the seam swap on the same data.

## Risks / watch-outs
- **Circular imports** — the `db/` package exists to prevent `api ⇄ ingest`. Don't import FastAPI
  into `db/` or `ingest/`.
- **`status` leak back into `jobs`** — the single biggest correctness trap. Ingest must write only
  the `jobs` table. If you ever see a fetch reset a status, this is why.
- **`first_seen_at` overwrite** — easy to clobber in an `ON CONFLICT DO UPDATE`; exclude it from the
  update SET list.
- **Windows native PG** — service/port/auth setup is the fiddly part; budget for it, document it.
- **Date types** — JSONL stores `posted_date` as a string; decide string vs `date` column and keep
  `from_record` tolerant (older records may be null/oddly formatted).

## Learning notes to write inline as you build (meta-goal)
- Why a repository layer between the ORM and the API seam (testability, no web stack in DB tests).
- ORM session lifecycle per request (FastAPI dependency / context-managed session) — a classic
  footgun if sessions leak across requests.
- `ON CONFLICT` upsert vs read-modify-write race (single-user now, but name the tradeoff).
- Alembic autogenerate's blind spots; why migrations are reviewed, not trusted.
- The payoff line: React + `api/main.py` + `api/models.py` change **zero lines** for the store swap —
  that's the seam thesis proven.

## Working norms (carry over)
- Branch off `main`; **propose nothing more — this IS the proposal.** Implementing agent codes after
  Chris green-lights. Don't commit until Chris says.
- Python via `./py.ps1` or the full interpreter path (`docs/ENV.md`). git via Bash tool; gh full path.
- Name each primitive choice + tradeoff as you go (learning is first-class).
