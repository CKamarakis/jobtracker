# HANDOFF — 2026-06-09 (repo now on GitHub; next = branch/PR/merge loop)

Transient note for the next session. Full rationale persisted in memory:
`project_state_2026-06-09.md` (+ `project_state_2026-06-03.md` for eval/rubric facts).

## Where we are (good state — nothing broken)
- **Repo is LIVE on GitHub, PUBLIC:** https://github.com/CKamarakis/jobtracker (user `CKamarakis`).
  Local `main` tracks `origin/main`; first commit `0d87125` pushed.
- **git + gh set up from scratch this session.** gh v2.93 authed as CKamarakis.
  gh lives at `C:\Program Files\GitHub CLI\gh.exe` (off PATH in bash → prepend
  `export PATH="$PATH:/c/Program Files/GitHub CLI"`).
- **Strict .gitignore:** personal data is LOCAL ONLY — `profile/`, `output/`,
  `data/dossiers/`, `evals/labeled/` + `labeled.json`, `.claude/settings.local.json`,
  `data/*.bak`. Loosen manually later if desired.
- **jobs.jsonl WIPED to empty** (was 1028 = raw-board bloat). Full backup at
  `data/jobs.jsonl.2026-06-04.bak` (gitignored). Re-fetch with tightened filters next.

## DO THIS NEXT — the branch/PR/merge teaching rep (Chris going to PLAN MODE)
1. Take Chris's pending "few changes" (had `profile/criteria.md` open) as the FIRST
   feature branch — don't commit to main directly.
2. Loop to teach end-to-end: `git switch -c <name>` → edit → `git add`/`commit` →
   `git push -u origin <name>` → `gh pr create` → review diff on github.com →
   `gh pr merge` → `git switch main && git pull`.

## Carry-over (from 2026-06-03, still open)
- Re-fetch a realistic pool (tighten arbeitnow keyword filter), then the FIRST real
  triage run on live data. LinkedIn leads pipeline (email→search→fetch ATS) unbuilt.
- DON'T micro-tune the rubric on the 18 gold cases (0 far misses = noise frontier).

## Env
Python: `%LOCALAPPDATA%\Programs\Python\Python314\python.exe` (full path — PATH is bash-mangled).
gh: `C:\Program Files\GitHub CLI\gh.exe`.
