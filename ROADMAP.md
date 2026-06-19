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
- **Stack:** React + **Tailwind v4 + shadcn/ui** (frontend) ↔ FastAPI (Python, matches existing
  `ingest/`) ↔ files now, **Postgres later**.
  - *Revised 2026-06-11 (Phase C):* dropped Material UI for **Tailwind + shadcn/ui**. Reason:
    higher current market/CV relevance (the combo Chris keeps seeing in ads) and it teaches CSS
    composition, not just a component API. Cost: more hand-built UI than MUI's batteries-included
    components. shadcn = copy-in components (Radix/Base UI + Tailwind), not an npm-locked library.
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
| **A** | Deepen + prove the core loop to a done-bar | local files | Low–Med | 1–2 sessions | ✅ done |
| **B** | Thin FastAPI serving jobs / profiles / dossiers as JSON | reads files | Low–Med | 1–2 sessions | ✅ shipped (#5) |
| **C** | React: list → detail page → routing → select → transient shortlist → work one-by-one | via API (files) | High | bulk of effort | ✅ shipped 2026-06-11 (#6) (Tailwind+shadcn, not MUI) |
| **C+** | App-triggered fetch+triage seam (ephemeral pool, seen-guard, claude-agent-sdk) | files | Med | — | ✅ shipped (#7) |
| **C++** | Dashboard · Go-fetch dialog · post-fetch review table · long-poll · rejected view · job modal · pagination · title pre-filter harden | files | Med–High | — | ✅ shipped (#8, #10, #11, current branch) |
| **D** | DB arrives: **persist** shortlist, notes, statuses, applied-dates (first WRITE endpoints, `PATCH /jobs/{id}`) | Postgres | Med–High | 2–4 sessions | ✅ shipped 2026-06-17 (branch `phase-d-postgres`) — review actions now survive a refresh |
| **E** | Stats dashboard | Postgres | Med | 1–3 sessions | not started |
| **F (step 2)** | Subagents → API endpoints, auth, hosting, generalize for others | Postgres | High | open-ended | not started |

\*Rough and pace-dependent.

### Phase D — ✅ SHIPPED 2026-06-17 (branch `phase-d-postgres`)
Went straight to Postgres + SQLAlchemy + Alembic behind the existing API seam — the
"swap backing store behind a stable API" lesson the roadmap was built around. (D-lite —
JSONL write-back — was considered and rejected: it would teach a throwaway WRITE path we'd
rip out weeks later.)

**What landed (vs. the spec below — all met):**
- `db/` package = the persistence engine (`engine.py`, `models.py`, `repository.py`,
  `seed.py`, `pg.ps1`); imports no web stack so `ingest` and `api` both use it.
- Three tables created via **Alembic** migration `0001_initial`; split schema exactly as specced.
- `api/data_source.py` job functions now **delegate to `db.repository`** — `api/main.py`'s
  read routes, `api/models.py`, and the entire React app changed **zero lines** for the swap
  (only added the new `PATCH` route + `window` param + a `notes` summary field). Seam thesis proven.
- `ingest/run.py` upserts into PG (never wipes); `last_seen_at` bumps, `first_seen_at` insert-only,
  human `status` survives a re-fetch (verified: re-upserting the 227-job pool kept a shortlisted
  job shortlisted, count unchanged).
- **First WRITE endpoint** `PATCH /jobs/{id}` live; React review actions (notes/remove/approve)
  now persist and survive a refresh — the Phase D acceptance test.
- Dashboard = durable-pool **windowed VIEW** (`/jobs?window=N`): fresh results + anything touched.
- **Store is portable Postgres** (EnterpriseDB binary build, port 5433, no installer/service/Docker;
  Docker still deferred → G6). Setup + rebuild steps in `docs/ENV.md`.

- **Store:** Postgres from day one (no SQLite-then-migrate). **Native install now; Docker
  deferred** (2026-06-17 — solo/local, Docker's reproducibility payoff isn't here yet; SQLAlchemy
  is connection-string-agnostic, so containerizing later is a config change, not a rewrite).
  → see backlog **G6**.
- **ORM/migrations:** SQLAlchemy + Alembic.
- **Seam:** `api/data_source.py` is where the swap lands — React never notices.
- **Schema = split (2026-06-17):** ingest data and human edits have opposite lifecycles
  (ad rows are re-fetched/overwritten daily; user edits are sacred), so they live apart:
  - `jobs` — source-owned ad data; re-fetch **upserts** (dedup-merge), never truncates.
    Adds `first_seen_at` (insert-only) + `last_seen_at` (bumped per upsert) alongside `posted_date`.
  - `job_actions` — sacred human edits keyed by job id: `status`, `applied_date`, lightweight `notes`.
    Re-fetch never touches this table; **status persists across re-fetches** (an approved/applied
    job re-encountered on the board stays approved/applied, never resets to `new`).
  - `application_notes` — only for jobs actually applied to: `notes`, `salary` (range string),
    `links`. On row create, the general `job_actions.notes` is **copied in once** — no ongoing sync.
- **Pool is durable, dashboard is a filtered view (not wipe-on-fetch).** Stop physically wiping.
  Dashboard query ≈ `WHERE last_seen_at = <this fetch> OR status != 'new'` — shows this run's
  fresh results **plus** anything you've touched; stale untouched `new` jobs just don't render.
  Same clean "last run" feel as wiping, but applications/edits never disappear.
- **First WRITE endpoints:** `PATCH /jobs/{id}` (status, notes, applied-date) — makes the
  currently LOCAL-ONLY review actions survive a restart.

## Future steps (requested 2026-06-17) — backlog, ordered by dependency

| # | Step | Maps to / depends on | Primitive | Notes |
|---|---|---|---|---|
| **G1** | **Company-scoped search** — run a search per company and bring results into the app | new endpoint + UI; uses existing `research` subagent + `dossier` skill | subagent + WebSearch/WebFetch | Surfaces a sourced dossier on demand from a job/company; refuses to invent (non-negotiable rule 2). |
| **G2** | **Cover-letter editor in-app** — draft + edit a letter inside a text editor in the UI | depends on **D** (need to persist edits); uses `cover-letter` subagent + `cover-voice` skill | subagent seeds draft, React rich-text editor | Draft pre-filled in fixed voice; human edits before save. Never auto-applies (rule 1). |
| **G3** | **Export cover letter → PDF** | depends on **G2** | client-side print/PDF or server render | Save the edited letter as a PDF artifact (→ `output/`, later DB/blob). |
| **G4** | **Application history** — list of applications with editable details (status, dates, notes) | depends on **D** (persistence) | DB-backed CRUD + React table | This IS the persisted side of Phase D made first-class: applied-dates, outcomes, editable rows. |
| **G5** | **Local triage model** — swap the triage LLM to a local model | the `api/triage_runner.py` seam (one file) | Ollama, **eval-gated** | Decided earlier: NOW = claude-agent-sdk on subscription ($0 marginal); LATER = local Ollama, ships only if it holds agreement on `evals/labeled.jsonl`. API-key path rejected as additive cost. |
| **G6** | **Containerize Postgres (Docker)** — move the native dev DB into docker-compose | follows **D** (native PG ships first) | Docker Compose | Deferred from D (2026-06-17): reproducibility payoff only matters with a 2nd machine/teammate/prod. SQLAlchemy is connection-string-agnostic, so this is a config swap, not a rewrite. |

**Dependency chain:** D (persistence) unlocks **G2/G4**; G2 unlocks **G3**. **G1** and **G5** are independent of D and can slot in anytime.

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
