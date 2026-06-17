# Jobhunt

A personal, local job-hunt assistant. It ingests job ads from public APIs daily, triages
them against written criteria, drafts cover letters in a fixed voice, and researches
companies into sourced dossiers — then surfaces a shortlist for review in a web app.

**Humans review and apply. This system never submits anything.**

It doubles as a hands-on tour of the Claude Code ecosystem — agents, skills, evals, and a
file-now / Postgres-later architecture behind a stable API seam.

## Stack
- **Ingestion** — Python (deterministic, no LLM): hits job APIs (Arbeitnow, Adzuna), dedups, writes JSONL.
- **Triage / cover-letter / research** — Claude Code subagents + skills, reading the candidate profile and writing files.
- **Backend** — FastAPI over the pipeline artifacts; `data_source.py` is the seam (files today, Postgres later).
- **Frontend** — React + TypeScript + Vite, Tailwind v4 + shadcn/ui.
- **Storage** — JSONL + `status.json` today → Postgres (SQLAlchemy + Alembic) next.

## Layout
| Path | What |
|------|------|
| `ingest/` | Daily fetch + dedup pipeline → `data/jobs.jsonl` |
| `api/` | FastAPI backend; `serve.ps1` runs it, Swagger at `/docs` |
| `web/` | React frontend (Vite dev server on :5173) |
| `profile/` | Candidate CV, triage criteria, cover template |
| `evals/` | Gold-set eval harness for triage quality |
| `.claude/` | Subagents + skills |

See `ROADMAP.md` for direction and `CLAUDE.md` for the operating manual.
