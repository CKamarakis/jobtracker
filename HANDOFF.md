# HANDOFF — 2026-06-16 (Dashboard + post-fetch results review screen SHIPPED; next = persist the review actions)

Transient note for the next session. **Authoritative living doc + full rationale:**
`C:\Users\Chris\.claude\plans\ok-this-is-the-generic-gizmo.md` (the plan file — read it first).
Persisted memory: `project_state_2026-06-15.md`, `project_triage_llm_seam.md`.

## What changed direction
We started building the **job-tracker app proper**, screen-by-screen, from Chris's 10 user
stories. Chris steers the pace and challenges decisions. This **supersedes** the old
"Phase D Postgres next" framing in prior handoffs. First screen = the **dashboard**, and its
"Go fetch" button forced the long-deferred "app triggers an AI action through the API" seam —
which is now built and proven.

## DONE & PROVEN this session (backend seam — Steps 1 & 2 of the plan)
- **Ephemeral pool:** `ingest/run.py` → `run_ingest(sources, duration)` **wipes & replaces**
  `data/jobs.jsonl` each run (scratch, not an accumulator). Source registry + duration→window
  mapping. `ingest/adzuna.py` got a `max_days_old` param.
- **Async fetch endpoint:** `api/main.py` → `POST /fetch` (runs in a daemon thread via
  `api/fetch_runner.py`), `GET /fetch/status` (poll: idle|running|done|error + phase + counts,
  mirrored to `data/run_status.json`), `GET /sources`.
- **Triage stage:** `api/triage_runner.py` — scores new jobs via **`claude-agent-sdk` against
  Chris's existing Claude subscription (~$0 marginal)**. Prompt = the real
  `.claude/agents/triage.md` body + `profile/*.md` inlined (single source of truth on disk).
  Pluggable provider boundary (`_score_batch_claude_sdk`) for a later local-Ollama/API swap.
- **Seen-guard:** `data/triage_cache.json` (job id → verdict). Wiped+refetched repeats hydrate
  free; only new ads hit the LLM. **Proven:** a server refetch hydrated 88/100 from cache,
  scored only 12 new, 0 failed. Verdicts are sound (87 reject / 1 fit / 37 prefiltered).

### Gotchas baked in (Windows + claude-agent-sdk) — don't reintroduce
- `system_prompt` is passed as a **CLI arg** → Windows ~32k cmdline cap (`WinError 206`, which
  the SDK mis-reports as "CLI not found"). Big content rides the **user message (stdin)**; only
  a short `SYSTEM_ROLE` goes in `system_prompt`.
- `max_turns=1` + an inlined "Read these first" instruction made the model attempt the Read
  tool → "Reached maximum number of turns" on ~half the batches. Fix in place: `allowed_tools=[]`
  + an override banner ("files inlined, do not use tools") + `max_turns=2`.

## DONE & SHIPPED this session (Step 3 — dashboard UI + post-fetch review screen)
Built screen-by-screen with Chris steering. The arc: dashboard → "Go fetch" → a dedicated
results-review table, with the async-run wait done **right** (one long-poll, no client polling).

- **Client layer** (`web/src/api/`): `request` generalised to take a `RequestInit`; added a
  `post<T>` helper + `listSources` / `triggerFetch` / `getFetchStatus` / `waitForFetch`. New
  `FetchStatus` / `FetchRequest` types mirror the Pydantic contract (verified vs live payload).
- **`DashboardPage`** (`/`): time-of-day greeting; **Go fetch** CTA → `GoFetchDialog`; empty-state
  applications table; reads `/fetch/status` once on load for a status line.
- **`GoFetchDialog`**: sources multiselect (`null` = "all", avoids seeding state via effect) +
  duration single-select → `POST /fetch` → navigates to `/results`.
- **`ResultsPage`** (`/results`): the post-fetch review queue, Chris's 7 columns:
  `# / Company / Title(ext-link new tab) / View(→/jobs/:id) / Notes / Remove / Approve`.
  Mount flow: read status → **if running, await `/fetch/wait`** (shows a spinner) → load pool.
  **Notes / Remove / Approve are LOCAL-ONLY (ephemeral) for now** — UX proven, no persistence.
- **`ui/dialog.tsx`**: new shadcn-style wrapper over **Base UI** Dialog (this kit is Base UI, not
  Radix → `render` props, not `asChild`). `Layout` got a nav bar; `/search` = old list page;
  `/applications` + `/saved` = `StubPage`.

### The long-poll (how "results appear when the run finishes" works — no heartbeat)
- `fetch_runner` has a `threading.Event` `_idle`: **set** when nothing runs, **cleared** in
  `start()`, **set again** in `_run`'s `finally` (fires on success *or* error).
- `GET /fetch/wait` → `_idle.wait(90)`: one HTTP request the server holds open until the run ends
  (90s cap bounds the hang; a timeout mid-run just means the client calls again). Returns instantly
  when idle (verified 39ms). This replaced an earlier 1.5s status-poll Chris (rightly) rejected.
- **Caveat:** a blocking sync endpoint holds one FastAPI threadpool thread (default 40) for ≤90s.
  Fine for single-user local; at scale use async + `asyncio.Event` or SSE/WebSocket push.

## DO THIS NEXT — persist the review actions (write endpoints)
The results screen is UX-complete but its three actions don't survive a reload. Wire them to the
backend (Chris deferred the semantics; confirm before building):
- **Approve** → likely `status='shortlisted'`; **Remove** → `status='skipped'` (soft, keeps the
  record) vs hard delete; **Notes** → a `notes` field on the job record + a write path.
- Needs the **first WRITE-to-data endpoints** (e.g. `PATCH /jobs/{id}`). The data seam
  (`api/data_source.py`) is read-only today — extend it to write back to `data/jobs.jsonl`.
- Then the dashboard **Applications** table (currently empty-state) can show approved jobs, and
  the results view can default to **hiding rejects** (pool is ~87 reject / few fit — flat 139 is noisy).

## State / housekeeping
- **Server:** a uvicorn may still be running on :8000 — restart fresh. Run:
  `$env:PYTHONUTF8=1; & "<py>" -m uvicorn api.main:app --port 8000`. If a stale server serves old
  code (a NEW route 404s but `/health` works), kill the PID on :8000 first (PowerShell:
  `Get-NetTCPConnection -LocalPort 8000 -State Listen | % { Stop-Process -Id $_.OwningProcess -Force }`).
- **`data/jobs.jsonl` = 139 fetched+triaged jobs** (old 193 pool backed up at
  `data/jobs.backup-pre-fetch-seam.jsonl`). `data/triage_cache.json` has 88 entries.
- **Deps added:** `claude-agent-sdk` (bundles its own Claude Code CLI; auth = Chris's existing
  Claude login, verified headless).

## Env (unchanged)
- Python: `C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe` (full path; UTF-8).
- git → Bash tool. gh → `"/c/Program Files/GitHub CLI/gh.exe"` from Bash tool.
- Node 24 / npm 11. `web/` = Vite + React 19 + TS + Tailwind v4 + shadcn. `npm run dev` → :5173.
