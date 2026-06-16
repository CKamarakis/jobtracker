"""api/data_source.py — THE SEAM (Phase B).

This is the single module the rest of the API talks to. Routes in `main.py` call
functions here; they never `open()` a file or know a path. Today every function
reads the existing pipeline artifacts (data/jobs.jsonl, profile/*.md, dossiers,
cover letters). In Phase D, Postgres replaces the *bodies* of these functions and
nothing else in the codebase changes — that is the whole "files now, DB later"
bet from ROADMAP.md, made concrete in one file.

Design rules:
- Read-only. Phase B serves; it does not mutate. Writes (shortlist, notes,
  applied-dates) arrive with the DB in Phase D, behind new functions here.
- No FastAPI/Pydantic imports. This layer returns plain dicts/strings so it stays
  swappable and unit-testable without the web stack. Shaping into response models
  is the route layer's job.
- Reuse the pipeline's own loader (ingest.store.load_jobs) so the API and the
  ingest code can never drift on how a record is parsed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo root = parent of this api/ package. All artifact paths derive from it, so the
# server can be launched from anywhere.
REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = REPO_ROOT / "data" / "jobs.jsonl"
PROFILE_DIR = REPO_ROOT / "profile"
DOSSIER_DIR = REPO_ROOT / "data" / "dossiers"
COVER_DIR = REPO_ROOT / "output" / "cover-letters"

# Reuse the ingest loader rather than re-parsing JSONL here (one source of truth for
# what a record looks like). ingest/ isn't an installed package, so add it to sys.path.
sys.path.insert(0, str(REPO_ROOT / "ingest"))
import store  # noqa: E402  (path-dependent import, intentional)


# Fields returned in LIST views. The full record (incl. the long `description`) is
# only sent on the detail endpoint — list payloads stay small for the React table.
SUMMARY_FIELDS = (
    "id", "source", "company", "title", "location", "remote",
    "url", "ats_url", "posted_date", "status", "triage_verdict", "triage_reason",
)


def _summary(rec: dict) -> dict:
    return {k: rec.get(k) for k in SUMMARY_FIELDS}


# --- Jobs ----------------------------------------------------------------------

def list_jobs(status: str | None = None, verdict: str | None = None) -> list[dict]:
    """All jobs as summaries, optionally filtered by status and/or triage_verdict.
    Sorted by verdict strength (strong fit → reject → untriaged), then company."""
    jobs = store.load_jobs(JOBS_PATH).values()
    rows = [
        _summary(r) for r in jobs
        if (status is None or r.get("status") == status)
        and (verdict is None or r.get("triage_verdict") == verdict)
    ]
    rows.sort(key=lambda r: (_VERDICT_ORDER.get(r.get("triage_verdict"), 99), (r.get("company") or "").lower()))
    return rows


def get_job(job_id: str) -> dict | None:
    """Full record (incl. description) for one job, or None if the id is unknown."""
    return store.load_jobs(JOBS_PATH).get(job_id)


_VERDICT_ORDER = {"strong fit": 0, "fit": 1, "stretch": 2, "reject": 3}


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
