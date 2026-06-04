# HANDOFF — 2026-06-03 (eval hardened; next = ingestion/Adzuna)

Transient note for the next session/chat. Delete once the Adzuna source is wired.
Full rationale persisted in memory: `project_state_2026-06-03.md`.

## Where we are (good state — nothing broken)
- **Eval is trustworthy now.** `evals/run_eval.py` runs at **temperature=0** (added this session).
  Latest baseline: **10 exact / 8 adjacent / 0 far** on the 18-job gold set.
  Log: `evals/runs/20260603-135108.json`. All disagreements are adjacent (off-by-one).
- **Company size is no longer a hard filter.** It's a graduated soft drag — **factor 10** in
  `profile/parameters.md` (never auto-rejects; outweighable by a moat; stacks toward reject).
  `criteria.md` + `CLAUDE.md` aligned. This killed the only far miss (Databricks) — proven win.
- **Prefilter is wired** into `ingest/run.py` (new-record branch only; stamps `skipped` +
  `skip_reason`, still stores; merged records untouched). Compiles; not yet run on a fresh fetch.

## DO THIS NEXT — ingestion rethink (the real leverage)
1. **Confirm the Adzuna dev key landed** in `.env` (Chris set it up in a parallel agent on 2026-06-03).
2. **Add `ingest/adzuna.py`** — a source whose `fetch()` returns records keyed via
   `store.job_key(...)` (don't hand-roll ids). Use Adzuna's **server-side params** (`what`,
   `where`, `category`, `country=de`) so we fetch a *realistic* pool, not 500 unfiltered rows.
   Register it by appending to `SOURCES` in `run.py`.
3. **Run `python ingest/run.py`** → realistic pool → then the **first real triage run** on
   live (non-labeled) data. The current 463-job pool is unrealistic (Arbeitnow has no
   server-side filter) — all 463 are still `status:"new"`, deliberately un-triaged.

## DO NOT do next
- **Don't micro-tune the rubric on these 18 cases.** 0 far misses = we're at the
  overfitting/noise frontier. Let the gold set grow from real triage disagreements and tune
  reactively. (The temp=0 fix is what makes that future tuning trustworthy.)

## Deferred rubric patterns (revisit at larger n, not now)
- **Altitude-floor cluster** (Raisin/eBay/ARCHIMED): agent softens "too junior / 12+yr bar /
  France on-site" to `stretch`; Chris rejects. Real + generalizable — top candidate for the
  next reactive pass.
- **Location hard-filter leak**: ARCHIMED France-on-site should `reject`.
- Kombo (parked young-founder), Amadeus (irreducible — forbidden product/offshore judgment).

## Env
Python: `%LOCALAPPDATA%\Programs\Python\Python314\python.exe` (full path — PATH is bash-mangled).
