"""api/data_source.py — THE SEAM (Phase B seam, Phase D store swap).

This is the single module the rest of the API talks to. Routes in `main.py` call
functions here; they never `open()` a file or know a path. Job reads/writes now go to
**Postgres** via the `db.repository` package (Phase D); the markdown docs (profile,
dossiers, cover letters) are still flat files. The job-function BODIES changed; their
signatures, the routes, the Pydantic models, and the React app did not — the whole
"files now, DB later behind a stable seam" bet from ROADMAP.md, made concrete in one file.

Design rules:
- No FastAPI/Pydantic imports. This layer returns plain dicts/strings so it stays
  swappable and unit-testable without the web stack. Shaping into response models
  is the route layer's job.
- Job reads/writes delegate to db.repository (Phase D). The markdown docs (profile,
  dossiers, cover letters) are still flat files — they were never the thing the DB
  was for, so they stay on disk behind the same seam.

PHASE D — the seam swap, made concrete: the job functions below changed their BODIES
to call db.repository instead of reading data/jobs.jsonl. Their signatures, the routes
in main.py, the Pydantic models, and the entire React app are UNCHANGED. That zero-line
ripple is the whole "files now, Postgres later behind a stable seam" thesis, proven.
"""

from __future__ import annotations

from pathlib import Path

from db import repository as repo

# Repo root = parent of this api/ package. Markdown-doc paths derive from it, so the
# server can be launched from anywhere. (Jobs no longer have a file path — they're in PG.)
REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = REPO_ROOT / "profile"
DOSSIER_DIR = REPO_ROOT / "data" / "dossiers"
COVER_DIR = REPO_ROOT / "output" / "cover-letters"


# Fields returned in LIST views. The full record (incl. the long `description`) is
# only sent on the detail endpoint — list payloads stay small for the React table.
SUMMARY_FIELDS = (
    "id", "source", "company", "title", "location", "remote",
    "url", "ats_url", "posted_date", "status", "triage_verdict", "triage_reason",
    "notes",  # lightweight human note; in the list so its indicator survives a refresh
)


def _summary(rec: dict) -> dict:
    return {k: rec.get(k) for k in SUMMARY_FIELDS}


# --- Jobs (delegated to db.repository — Phase D) -------------------------------

def list_jobs(status: str | None = None, verdict: str | None = None) -> list[dict]:
    """All jobs as summaries, optionally filtered by status and/or triage_verdict.
    Sorted by verdict strength (strong fit → reject → untriaged), then company."""
    return [_summary(r) for r in repo.list_jobs(status=status, verdict=verdict)]


def dashboard_jobs(window_days: int = 1) -> list[dict]:
    """Durable-pool VIEW as summaries: this run's fresh results PLUS anything touched.
    Replaces the old wipe-on-fetch — see db.repository.dashboard_jobs."""
    return [_summary(r) for r in repo.dashboard_jobs(window_days=window_days)]


def get_job(job_id: str) -> dict | None:
    """Full record (incl. description) for one job, or None if the id is unknown."""
    return repo.get_job(job_id)


def patch_job_action(job_id: str, status: str | None = None, notes: str | None = None,
                     applied_date: str | None = None) -> dict | None:
    """Persist a human review action (status/notes/applied-date). First WRITE path through
    the seam. Returns the updated full record, or None if the job id is unknown."""
    return repo.patch_action(job_id, status=status, notes=notes, applied_date=applied_date)


# --- Profile / dossiers / cover letters (markdown blobs) -----------------------

def _list_md(directory: Path) -> list[str]:
    """Slugs (filename without .md) of markdown files in a directory, sorted."""
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.md"))


def _read_md(directory: Path, slug: str) -> str | None:
    """Raw markdown text for one slug, or None. Slug is sanitized to a bare stem to
    prevent path traversal (no '..', no separators reach the filesystem)."""
    safe = Path(slug).stem
    path = directory / f"{safe}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def list_profiles() -> list[str]:
    return _list_md(PROFILE_DIR)


def get_profile(name: str) -> str | None:
    return _read_md(PROFILE_DIR, name)


def list_dossiers() -> list[str]:
    return _list_md(DOSSIER_DIR)


def get_dossier(slug: str) -> str | None:
    return _read_md(DOSSIER_DIR, slug)


def list_cover_letters() -> list[str]:
    return _list_md(COVER_DIR)


def get_cover_letter(slug: str) -> str | None:
    return _read_md(COVER_DIR, slug)
