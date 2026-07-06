# Job-Hunt Automation — Operating Manual

This repo helps a senior product/eng leader (Berlin) find and apply to roles. It
ingests jobs from APIs daily, triages them against written criteria, drafts cover
letters, and researches companies. **Humans review and apply. This system never
submits anything.**

## Working norms — LEARNING IS THE PRIMARY GOAL
**Read this first.** Chris is using this repo to learn the Claude Code ecosystem
end-to-end — project structure, when to use agents vs. subagents vs. skills vs.
MCPs vs. external tools, how to build and iterate on evals, what good vs. bad
practice looks like. Shipping the job-triage system matters, but **teaching
matters more**. If a choice is between "ship faster" and "teach better", choose
teach better. Explanation is not commentary on the work — it IS the work.

- **Inline:** when a tool/primitive choice is made, one or two sentences naming
  the reason and the tradeoff. Lean — no tutorial framing.
- **Milestone:** at the end of a logical chunk (a finished subagent, a working
  skill, an eval run), a 5-10 line writeup of what primitive was used, why,
  and one good-practice or gotcha worth remembering.
- Frame for a senior practitioner (Chris has real eng depth). Don't over-explain
  basics, but never skip the *why* on a Claude-Code-specific decision.
- No sugarcoating, no fixating, no hallucination. Say what you don't know.

## Non-negotiable rules
1. **Never auto-apply.** The final step is always a draft + shortlist for human review.
2. **Never invent facts.** Funding, revenue, headcount, dates: if not found, write
   `unknown / not disclosed`. Cite a source URL for every researched claim. A wrong
   number is worse than a blank.
3. **Cover-letter voice is fixed.** Confident but warm, conversational, no buzzwords,
   no fluff, no metrics (the CV carries those), ~250 words. Rules live in
   `.claude/skills/cover-voice/SKILL.md`. Do not improvise voice.
4. **German language — nuanced reject.** Candidate is conversational (B2). Reject ONLY
   when the ad explicitly states C1/native German as a *must* requirement (typically
   German-market-facing roles). Do not reject for "German a plus", "nice to have", or
   unspecified. When in doubt, keep it and flag the language bar in the anti-fit notes.
   See `profile/criteria.md`.

## Architecture (read this before building)
- **Ingestion is deterministic code, not an agent.** `ingest/*.py` hits job APIs,
  enriches LinkedIn leads, dedups, and writes JSONL. It runs daily and contains no
  LLM judgment, so it cannot hallucinate and is cheap to run unattended.
- **Three subagents, each with isolated context** (`.claude/agents/`):
  - `triage` — scores the deduped pool against `profile/criteria.md`, outputs a fit matrix.
  - `cover-letter` — drafts one letter per selected job using the cover-voice skill.
  - `research` — builds a company dossier (web search + fetch), refuses to invent.
- **Two skills** (`.claude/skills/`) encode reusable format/voice: `cover-voice`, `dossier`.
- **The candidate profile lives in `profile/`** and fits in context — no RAG needed now.
  (A future RAG corpus could be built from accumulated dossiers; not in scope yet.)

### Application layers (the pipeline now has a UI on top)

The repo grew from a CLI pipeline into a local app. Build around the working logic; swap
the backing store later behind a stable seam. (Full phase history in `ROADMAP.md`.)
- **`api/` — FastAPI over the pipeline artifacts.** Read endpoints for jobs / profile /
  dossiers / cover-letters; `POST /fetch` + `GET /fetch/wait` (long-poll) trigger an
  ingest+triage run. App-triggered triage runs via `claude-agent-sdk` on Chris's
  subscription ($0 marginal). Control script: `api/serve.ps1`; Swagger at `/docs`.
- **`api/data_source.py` IS the architectural seam.** Everything reads through it.
  Files are behind it today; **Postgres lands behind it in Phase D** and the React app
  never notices. Do not bypass it.
- **`web/` — React + Tailwind v4 + shadcn/ui (not MUI).** Dashboard → Go-fetch dialog →
  post-fetch review table → job-detail modal → rejected view. Vite dev server on :5173.
- **Review actions (notes / remove / approve) are LOCAL-ONLY today** — they do not survive
  a refresh. Phase D (Postgres + first WRITE endpoints, `PATCH /jobs/{id}`) fixes that.

## Job sources
- **Arbeitnow** — free, no key. ATS-sourced (Greenhouse, Personio, Workable, Recruitee,
  Lever, Ashby…), strong Berlin / German-market / 50–250-person coverage. Primary source.
- **Adzuna** — free dev key (`country=de`). Broader aggregator, wider net.
- **LinkedIn (leads only)** — alert emails give title + company + link, NOT full text.
  Pipeline: email lead → web-search `"{title}" {company} careers` → fetch the canonical
  ATS/careers page → full description → then triage normally. Manual paste is the fallback.
- Apify/LinkedIn paid actor: optional, later.
- **Active in the pipeline:** Arbeitnow + Adzuna (both registered in `ingest/run.py`'s
  `SOURCES`). `ingest/jobspy_source.py` exists but is **not** registered yet — wire it into
  `SOURCES` to enable. Add any new source the same way (register its `fetch()`).

## Data conventions
- Storage **today** is **JSONL** (one job per line) + `data/status.json`, read through
  `api/data_source.py`. **Phase D swaps this for Postgres behind that same seam** — the
  record shape and dedup rules below stay; only the store changes.
- **Dedup key** = stable hash of `lower(company) + normalized(title) + location`.
  Dedup runs **across sources AND across every daily run** — LinkedIn alert emails
  resend the same ads constantly, so before adding any job, check its key against the
  existing `data/jobs.jsonl`. If the key already exists, do not re-add; merge instead
  (keep the richest description, union the source list, keep the earliest posted_date,
  and preserve the existing `status` so a triaged/applied job never resets to `new`).
- Each job record: `id, source, company, title, location, remote, url, ats_url,
  description, posted_date, status` (`new|shortlisted|applied|skipped`).

## Triage output (the "Info function")
For each job, lean bullets:
- **Fit (you ↔ role):** why it's a good stage for the candidate's range, and why he fits.
- **Anti-fit:** where it falls short or where he's a stretch. Be honest, no salesmanship.
- **Verdict:** `strong fit | fit | stretch | reject` + one-line reason.
- **Links:** job ad URL + company website.
Apply hard filters first (see `profile/criteria.md`): >3yrs exp, ≥70% hard-criteria match,
German rule above. Reject before scoring if a hard filter fails. (Company size is a graduated
soft drag, not a hard filter — see factor 10 in `profile/parameters.md`.)
**Order the output by verdict, strongest first:** `strong fit` → `fit` → `stretch` →
`reject` (rejects collapsed to a short list at the bottom with their one-line reason).

## Evals (triage quality)
- `evals/labeled.jsonl` is the gold set: ~25 real jobs with the candidate's own past
  verdicts. `evals/run_eval.py` feeds them **blind** to the triage agent and reports
  agreement rate + a list of disagreements.
- The disagreements are the point: each one is an unwritten criterion. Articulate it,
  add it to `profile/criteria.md`, re-run. That loop is how triage improves.

## Commands

> **TOOLING PATHS — DON'T SEARCH, DON'T RABBIT-HOLE.** `python`/`git`/`gh`/`node`/`npm`
> are NOT reliably on the Claude tool PATH (stale-session gotcha). Never probe with
> `where`/`Get-Command`/`Test-Path`/Glob to "find" them — use the verbatim paths below.
> Full rationale: `docs/ENV.md`.

| Tool | Use it like this |
|------|------------------|
| **python** | `./py.ps1 <args>` from repo root, **or** `$env:PYTHONUTF8=1; & "C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe" <args>` (UTF-8 prefix avoids cp1252 errors on German text). |
| **git** | Run via the **Bash tool** (git is on its PATH there; PowerShell's is unreliable). Binary: `C:\Program Files\Git\cmd\git.exe`. |
| **gh** | Full path **from the Bash tool** so it inherits git: `"/c/Program Files/GitHub CLI/gh.exe" …`. Never bare `gh` in PowerShell ("unable to find git executable"). |
| **node/npm** | Lives at `C:\Program Files\nodejs` (on integrated-terminal PATH via `.vscode/settings.json`). If a fresh shell can't find it: `$env:PATH = "C:\Program Files\nodejs;$env:PATH"; & "C:\Program Files\nodejs\npm.cmd" <args>`. |

- `./py.ps1 ingest/run.py` — fetch + enrich + dedup → `data/jobs.jsonl` (daily).
- Ask Claude: *"triage the new jobs"* → invokes the triage subagent.
- `./py.ps1 evals/run_eval.py` — score triage against the gold set.
- `api/serve.ps1` — run the FastAPI backend (Swagger at `/docs`).
- `cd web; npm run dev` — frontend dev server → Vite on http://localhost:5173.

### Dev-stack control — ONE COMMAND, TRUST ITS OUTPUT (hard rule)

Starting/stopping the stack must take seconds, not minutes. The friction is never the
scripts — it's the assistant re-verifying by hand. Enforce:

- **Start:** run `./up.ps1` (or `./down.ps1`) **once, in the FOREGROUND.** Never wrap it
  in `Measure-Command` and never launch it with `run_in_background` — that buffers its
  output and orphans/kills the spawned servers.
- **The script's printed lines ARE the verification.** `up.ps1` already probes `/health`,
  `pg.ps1` uses `pg_isready`, `serve.ps1` polls before printing "ready." So after running
  it, **report its output verbatim and STOP.** Do **not** run any follow-up probe
  (`pg_isready`, `Invoke-RestMethod /health`, `Get-NetTCPConnection`, port checks). Those
  are redundant, each costs a permission prompt + round-trip, and are the entire reason
  this ever felt slow.
- Only diagnose further if the script itself prints `FAILED`.

## Reference files
- `profile/cv.md` — full CV. `profile/criteria.md` — triage rules. `profile/cover-template.md` — master letter.
- `profile/parameters.md` — scoring factors (incl. factor 10, company-size soft drag).
- `profile/experience-map.md` — depth-tagged capability surface read by triage.
- Salary anchors, target companies, and preferences live in `profile/criteria.md`.
- `ROADMAP.md` — phase history + what's next. `docs/ENV.md` — full tooling-path rationale.