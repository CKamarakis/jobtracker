# Roadmap — from job-hunt pipeline → personal job-tracker app

Tracking doc for the project's direction. Edit as phases close or decisions change.

## Context
Today the repo is a deterministic Python ingestion pipeline (`ingest/*.py` → `data/jobs.jsonl`)
plus three Claude Code subagents (triage / cover-letter / research) that read and write files.
No UI, no database. The goal is to grow an **application on top of the working logic** — first a
personal tool to *view, inspect, and work through* the jobs the pipeline finds; later (step 2) a
product others can use.

**Guiding principle:** build around working logic; change the backing store later behind a stable
seam. The core loop needs no database — it produces files. The database only earns its place once
Chris wants his *own actions* (shortlist, notes, applied-dates) to survive a restart. The UI comes
**before** the DB and reads the existing files through a thin API.

## Architecture decisions (locked)
- **Monolith, single repo.** Microservices is overhead for a single-user local tool.
- **Stack:** React + Material UI (frontend) ↔ FastAPI (Python, matches existing `ingest/`) ↔
  files now, **Postgres later**.
- **The API is the stable contract.** Files behind it first; Postgres behind it later; the React
  frontend never notices the swap. This seam makes "files now, DB later" free.
- **When the DB arrives it's Postgres from day one** (not SQLite-then-migrate): no dialect drift,
  dev/prod parity, learn the production DB directly. Local Postgres via Docker. **SQLAlchemy**
  (ORM) + **Alembic** (migrations) — both deferred until Phase D.
- **Subagents stay in Claude Code for now**; outputs land in files (later DB). Moving them behind
  API endpoints calling the Claude API is the step-2 product pivot (Phase F).

## Phases

| Phase | Milestone | Backing store | Complexity | Rough time* | Status |
|---|---|---|---|---|---|
| **A** | Deepen + prove the core loop to a done-bar | local files | Low–Med | 1–2 sessions | in progress |
| **B** | Thin FastAPI serving jobs / profiles / dossiers as JSON | reads files | Low–Med | 1–2 sessions | not started |
| **C** | React + MUI: list → profile page → routing → select → transient shortlist → work one-by-one | via API (files) | High | bulk of effort | not started |
| **D** | DB arrives: persist shortlist, notes, statuses, applied-dates | Postgres | Med–High | 2–4 sessions | not started |
| **E** | Stats dashboard | Postgres | Med | 1–3 sessions | not started |
| **F (step 2)** | Subagents → API endpoints, auth, hosting, generalize for others | Postgres | High | open-ended | not started |

\*Rough and pace-dependent. Phase C (React) is the softest estimate if it's newer ground.

## Learning focus per phase (the meta-goal)
- **A** — deterministic code vs. agents; the eval→criteria→re-run loop; prompt/criteria iteration.
- **B** — REST API design; **API-as-contract** pattern; Pydantic models; serving JSON; CORS; hiding the data source behind an interface.
- **C** — React fundamentals (components, hooks, state); client-side **routing**; the MUI component system; data fetching; list/detail UI patterns; transient (non-persisted) state.
- **D** — schema design; Postgres; SQLAlchemy ORM; Alembic migrations; **swapping a backing store behind a stable API**; Docker for local PG.
- **E** — SQL aggregation (`GROUP BY`); React charting (Recharts / MUI X Charts); metric derivation.
- **F** — auth (sessions / JWT / OAuth); multi-tenancy; calling the Claude API from a backend; hosting; secrets.

## Phase A done-bar
The file-based core is "working enough" to start the UI when:
- A realistic pool is ingested (filters tightened so it isn't raw-board bloat).
- One real triage run on live data produces verdicts Chris trusts (eval agreement acceptable).
- Hand-pick → research yields a dossier he'd actually use; cover letter drafts in voice.
- **LinkedIn-leads pipeline: OUT of Phase A** (deferred — just more rows in the same shape).
