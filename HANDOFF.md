# HANDOFF — 2026-06-16 (PR #10 merged: title pre-filter hardened + rejected-jobs view; next = persist review actions OR eval backstop)

Transient note for the next session. **Authoritative living doc + full rationale:**
`C:\Users\Chris\.claude\plans\ok-this-is-the-generic-gizmo.md` (the plan file — read it first).
Persisted memory: `project_state_2026-06-16.md` (Step 3 UI) and `project_dedup_prefilter.md`.

## State / housekeeping
- **On `main` @ `47764e1`**, current with origin. PRs #8 #9 #10 all merged. No open branches.
- **Servers may still be running** from this session: uvicorn on :8000, Vite on :5173.
  Restart fresh if stale. Backend:
  `$env:PYTHONUTF8=1; & "<py>" -m uvicorn api.main:app --port 8000`.
  If a NEW route/field 404s/empties but `/health` works → stale server serving old code; kill PID:
  `Get-NetTCPConnection -LocalPort 8000 -State Listen | % { Stop-Process -Id $_.OwningProcess -Force }`.
- **`data/jobs.jsonl` is the LAST run's pool** (227 fetched; 21 passed triage / 157 reject /
  49 title-prefiltered-skipped). These verdicts predate the new filter — a fresh "Go fetch"
  rebuilds the pool and far fewer jobs will reach triage.

## DONE & MERGED this session (PR #10)
Two threads, one PR.

### 1. Title pre-filter hardening (`ingest/filters.py`) — the big one
The `\b`-bounded denylist was leaking obvious non-fits to the **paid LLM triage** stage.
- **Split into TWO regexes** because German compounds defeat `\b`:
  - `_TITLE_DENY_STEM` — **substring** (no boundaries). For compounding/inflecting German
    stems where `\b` silently fails: `\bpraktikum\b` never matched `Pflichtpraktikum`;
    `\bcontroller\b` never matched `Vertriebscontroller`; `\bgrafik\b` never matched
    `Grafikdesign`; the pre-existing `buchhalt` was a **dead rule** (never matched
    `Buchhalter`). This was a latent bug, not just a gap.
  - `_TITLE_DENY_WORD` — **`\b`-bounded**, for real English/short words that WOULD
    over-match as substrings (e.g. `qa`). Key trick: **`engineers?` not `engineering`** —
    cuts IC "Software/Staff/Laravel Engineer" but lets a coupled
    "Head of Product & Engineering" (a real strong fit) through to triage.
- **Added the leaking families:** eng/IT IC, finance/controlling, project/claim/quality
  mgmt, marketing/SEO, data scientist/analyst, consultant/berater, sales/bizdev, people/HR,
  trades/field-service, safety/environment, retail/callcenter, property mgmt.
- **Validated rigorously** (the disciplined loop — do this for any future denylist change):
  ran the new filter against **all 18 `evals/labeled/*.md` gold titles** AND the live
  227-pool. Result: **178 → 57 jobs reach the LLM**, **0 gold regressions, 0 of the 21
  keepers cut.** Deliberately dropped bare `growth` (a Growth PM is still a PM → recall).
- **The floor:** what still passes is mostly genuine "Product Manager/Owner" titles that
  only the BODY disqualifies (German-C1, wrong domain). Titles can't cut those without
  eating the target family — that's triage's job. ~57 is about the responsible floor.

### 2. Rejected-jobs view (frontend + thin API touch)
- Post-fetch `/results` now shows **ONLY what passed triage** (strong fit/fit/stretch).
- New **read-only `/results/rejected`** page (`web/src/pages/RejectedPage.tsx`), reached via
  a dashed CTA above the results table. Shows **triage rejects only** (title-prefiltered
  jobs are excluded — Chris's call), columns: #/Company/Title(ext)/Why-rejected/View.
- Surfaced `triage_reason` end-to-end. **GOTCHA:** `api/data_source.py` has a
  `SUMMARY_FIELDS` whitelist that projects records BEFORE the Pydantic model — adding the
  field to `models.py` alone wasn't enough; it must also be in `SUMMARY_FIELDS`.

### 3. Small UI fixes
- Logo `Job-Hunt` → `JobHunt`; dashboard greeting copy; fetch spinner centered (`min-h-[70vh]`)
  + 2× on desktop (`md:` variants).

## DO THIS NEXT — pick one (both still open, unchanged by this session)
1. **Persist the review actions** (the bigger deferred item). Results-page Approve/Remove/Notes
   are still LOCAL-ONLY/ephemeral. Needs the **first WRITE-to-data endpoints** (e.g.
   `PATCH /jobs/{id}`); `api/data_source.py` is read-only today — extend it to write back to
   `data/jobs.jsonl`. Semantics to confirm with Chris first: Approve→`shortlisted`?
   Remove→`skipped`(soft) vs hard-delete? Notes→new `notes` field? Then the dashboard
   Applications table can show approved jobs.
2. **Eval backstop for the new filter** (cheap, repo-aligned). Add 3–4 of the now-cut IC
   titles (Software Engineer, QA Analyst, Projektmanager, Marketing Manager) as labeled
   `reject` cases so a future loosening of `filters.py` can't silently regress. NOTE:
   `evals/labeled.json` is EMPTY (0 bytes) — the real gold set is the 18 `evals/labeled/*.md`
   files (parse `title:` / `verdict:` from each).

## Env (unchanged)
- Python: `C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe` (full path; UTF-8).
- git → Bash tool. gh → `"/c/Program Files/GitHub CLI/gh.exe"` from Bash tool.
- Node 24 / npm 11 at `C:\Program Files\nodejs`. `web/` = Vite + React 19 + TS + Tailwind v4 +
  shadcn-over-Base-UI. `cd web; npm run dev` → :5173. Typecheck: `npx tsc -p web/tsconfig.app.json --noEmit`.
