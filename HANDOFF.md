# HANDOFF — 2026-06-15 (Dashboard app started; backend fetch+triage seam DONE; next = Step 3 dashboard UI)

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

## DO THIS NEXT — Step 3: dashboard UI (`web/`)
Build against the endpoints above. Spec (Chris's): time-of-day greeting; **"Go fetch"** CTA →
shadcn `Dialog` with **sources multiselect** (from `GET /sources`) + **duration single-select**
(1 day / 3 days / 1 week) → `POST /fetch` → poll `GET /fetch/status` (ingest→triage→done) → on
done route to the list. Hero "applications" table = **empty state** for now (no apply flow yet).
Nav links to `/applications` + `/saved` (stub pages) and `/search` (reuse current list page).
- New `DashboardPage` at `/`; move current `JobListPage` to `/search`; keep `/jobs/:id`.
- `web/src/api/client.ts` is GET-only — add a POST helper + the `/fetch`, `/fetch/status`,
  `/sources` calls. Reuse the `useAsync` hook. No speculative list filters yet (build on felt need).

## State / housekeeping
- **Server:** a uvicorn from this session may still be running on :8000 — restart fresh.
  Run: `$env:PYTHONUTF8=1; & "<py>" -m uvicorn api.main:app --port 8000`. If a stale server
  serves old code (e.g. a route 404s but `/health` works), kill the PID on :8000 first.
- **`data/jobs.jsonl` = 139 freshly fetched+triaged jobs** (the old 193 pool is backed up at
  `data/jobs.backup-pre-fetch-seam.jsonl`). `data/triage_cache.json` has 88 entries.
- **Branch FLAG:** all backend work is **uncommitted on `phase-c-react-frontend`** (which also
  has open **PR #6** for the older frontend). Decide branching/commit before stacking Step 3.
- **Deps added:** `claude-agent-sdk` (bundles its own Claude Code CLI; auth = Chris's existing
  Claude login, verified working headless).

## Env (unchanged)
- Python: `C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe` (full path; UTF-8).
- git → Bash tool. gh → `"/c/Program Files/GitHub CLI/gh.exe"` from Bash tool.
- Node 24 / npm 11. `web/` = Vite + React 19 + TS + Tailwind v4 + shadcn. `npm run dev` → :5173.
