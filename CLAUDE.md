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

## Job sources
- **Arbeitnow** — free, no key. ATS-sourced (Greenhouse, Personio, Workable, Recruitee,
  Lever, Ashby…), strong Berlin / German-market / 50–250-person coverage. Primary source.
- **Adzuna** — free dev key (`country=de`). Broader aggregator, wider net.
- **LinkedIn (leads only)** — alert emails give title + company + link, NOT full text.
  Pipeline: email lead → web-search `"{title}" {company} careers` → fetch the canonical
  ATS/careers page → full description → then triage normally. Manual paste is the fallback.
- Apify/LinkedIn paid actor: optional, later.

## Data conventions
- Storage is **JSONL** (one job per line) + `data/status.json`. No database.
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
> **PYTHON PATH — DO NOT SEARCH FOR IT. EVER.** `python`/`py` are NOT on the Claude
> tool PATH (stale-session PATH gotcha). The interpreter is always at this exact path —
> use it verbatim, never run `where`/`Get-Command`/`Test-Path` to "find" it:
> ```
> C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe
> ```
> Prefix UTF-8 to avoid cp1252 errors on German text. Canonical invocation:
> ```powershell
> $env:PYTHONUTF8=1; & "C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe" <args>
> ```
> Or just call `./py.ps1 <args>` from repo root (thin wrapper, same thing).

> **GIT / GH PATHS — SAME RULE, DON'T SEARCH, DON'T RABBIT-HOLE.** Same stale-PATH
> gotcha hits `git` and `gh`, and they split across shells. Do NOT probe with
> `where`/`Get-Command`/Glob — use these verbatim:
> - **`git`** → use the **Bash tool** (git is on its PATH). PowerShell's is unreliable.
> - **`gh`** → call its full path **from the Bash tool** so it inherits git, e.g.:
>   ```
>   "/c/Program Files/GitHub CLI/gh.exe" pr create --base main --head <branch> --title "…" --body "…"
>   ```
> - Never run bare `gh` in PowerShell (it can't find git → "unable to find git executable").
> - Exact locations (already on integrated-terminal PATH via `.vscode/settings.json`):
>   `C:\Program Files\GitHub CLI\gh.exe` · `C:\Program Files\Git\cmd\git.exe`.

> **NODE / NPM PATHS — SAME RULE.** Same stale-PATH gotcha hits `node`/`npm`/`npx`
> (and `npm.cmd` shells out to `node`, so finding npm isn't enough — node's dir must
> be on PATH too). Don't probe with `where`/`Get-Command`/Glob. Node lives at
> `C:\Program Files\nodejs` (now on the integrated-terminal PATH via `.vscode/settings.json`).
> If a fresh shell still can't find it, prepend it inline:
> ```powershell
> $env:PATH = "C:\Program Files\nodejs;$env:PATH"; & "C:\Program Files\nodejs\npm.cmd" run dev
> ```
> Frontend dev server: `cd web; npm run dev` → Vite on http://localhost:5173.

- `python ingest/run.py` — fetch + enrich + dedup → `data/jobs.jsonl` (daily).
- Ask Claude: *"triage the new jobs"* → invokes the triage subagent.
- `python evals/run_eval.py` — score triage against the gold set.

## Reference files
- `profile/cv.md` — full CV. `profile/criteria.md` — triage rules. `profile/cover-template.md` — master letter.
- Salary anchors, target companies, and preferences live in `profile/criteria.md`.