"""db/repository.py — plain functions over the ORM (the only DB API the app calls).

Why a repository layer between the ORM and the data_source seam, rather than letting
data_source touch Session directly:
  - Testability: these are plain functions taking/returning dicts; you can exercise the
    DB without spinning up FastAPI.
  - One place owns session lifecycle (via engine.session_scope), so no ORM objects leak
    across request boundaries (a classic detached-instance footgun).
  - data_source keeps its exact signatures; only its bodies delegate here. That is the
    "swap the store behind a stable seam" deliverable.

Records crossing this boundary are plain dicts shaped like the old JSONL record, so
api/models.from_record and the React app need zero changes. `status` is folded in from
job_actions here (absence of a row ⇒ "new").
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .engine import session_scope
from .models import ApplicationNote, Job, JobAction

# Reuse the pipeline's canonical merge rules (richer description, union sources, earliest
# date, status preserved) instead of re-expressing them in SQL — that guarantees the
# cross-run merge can't drift from the cross-source merge ingest/run.py already does.
# ingest/store.py is leaf (stdlib only), so db -> store is acyclic; ingest -> db still holds.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))
import store  # noqa: E402  (path-dependent import, mirrors api/data_source.py)

# Verdict strength ordering (untriaged/None sinks to the bottom) — mirrors the old
# data_source._VERDICT_ORDER so list ordering is unchanged after the swap.
_VERDICT_ORDER = {"strong fit": 0, "fit": 1, "stretch": 2, "reject": 3}

# Columns ingest is allowed to overwrite on a re-fetch upsert. Excludes id (the conflict
# key) and first_seen_at (insert-only — overwriting it is the subtle clobber the plan warns
# about). last_seen_at is handled explicitly (bumped to now()).
_JOB_AD_COLUMNS = (
    "source", "company", "title", "location", "alt_locations", "remote",
    "url", "ats_url", "description", "posted_date", "posted_ts",
    "triage_verdict", "triage_reason", "triaged_date", "skip_reason",
)


# --- record <-> dict mapping ---------------------------------------------------

def _derived_status(job: Job, action: JobAction | None) -> str:
    """Effective status seen by the rest of the app. Human action wins; absent that, an
    ingest pre-filter drop (skip_reason set on the jobs row) reads as 'skipped' so triage
    skips it exactly like before — without ingest ever writing the human job_actions table.
    Everything else is 'new'."""
    if action and action.status:
        return action.status
    return "skipped" if job.skip_reason else "new"


def _job_to_dict(job: Job, action: JobAction | None) -> dict:
    """ORM row(s) → the flat JSONL-shaped record the rest of the app expects.
    `status` is derived (human action, else pre-filter, else 'new'); ad columns come from jobs."""
    rec = {
        "id": job.id,
        "source": job.source or [],
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "alt_locations": job.alt_locations,
        "remote": job.remote,
        "url": job.url,
        "ats_url": job.ats_url,
        "description": job.description,
        "posted_date": job.posted_date,
        "posted_ts": job.posted_ts,
        "triage_verdict": job.triage_verdict,
        "triage_reason": job.triage_reason,
        "triaged_date": job.triaged_date,
        "skip_reason": job.skip_reason,
        "status": _derived_status(job, action),
    }
    if action:
        rec["notes"] = action.notes
        rec["applied_date"] = action.applied_date.isoformat() if action.applied_date else None
    return rec


def _ad_columns(rec: dict) -> dict:
    """Pick only the source-owned ad columns out of an incoming record (drops status/notes
    so ingest can never write a human field). None values are kept — they're valid ad data."""
    return {k: rec.get(k) for k in _JOB_AD_COLUMNS if k in rec}


# --- reads ---------------------------------------------------------------------

def _rows_with_actions(session: Session, jobs: list[Job]) -> list[dict]:
    return [_job_to_dict(j, j.action) for j in jobs]


def list_jobs(status: str | None = None, verdict: str | None = None) -> list[dict]:
    """All jobs as flat records, optionally filtered by status / triage_verdict.
    Sorted by verdict strength (strong fit → reject → untriaged), then company."""
    with session_scope() as session:
        jobs = session.scalars(select(Job)).all()
        rows = _rows_with_actions(session, list(jobs))
    rows = [
        r for r in rows
        if (status is None or r.get("status") == status)
        and (verdict is None or r.get("triage_verdict") == verdict)
    ]
    rows.sort(key=lambda r: (_VERDICT_ORDER.get(r.get("triage_verdict"), 99), (r.get("company") or "").lower()))
    return rows


def get_job(job_id: str) -> dict | None:
    """Full flat record for one job, or None if the id is unknown."""
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None
        return _job_to_dict(job, job.action)


def dashboard_jobs(window_days: int) -> list[dict]:
    """The durable-pool VIEW: this run's fresh results PLUS anything the human has touched.

    A job renders if it's recent enough (posted within window_days) OR its status is no
    longer 'new' (approved/applied/skipped/noted stays regardless of age). Stale untouched
    `new` jobs simply don't show — same clean 'last run' feel as the old wipe, but human
    edits never disappear. Freshness is measured on posted_ts (epoch) to dodge the JSONL's
    inconsistent posted_date string formats.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - window_days * 86400
    out: list[dict] = []
    with session_scope() as session:
        for job in session.scalars(select(Job)):
            action = job.action
            fresh = job.posted_ts is not None and job.posted_ts >= cutoff
            # "Touched" = a real human action row with a non-new status — NOT an ingest
            # pre-filter skip. So stale pre-filtered rejects fall off; approved/applied stay.
            touched = action is not None and (action.status or "new") != "new"
            if fresh or touched:
                out.append(_job_to_dict(job, action))
    out.sort(key=lambda r: (_VERDICT_ORDER.get(r.get("triage_verdict"), 99), (r.get("company") or "").lower()))
    return out


# --- writes --------------------------------------------------------------------

def upsert_jobs(records: list[dict]) -> dict:
    """Insert-or-merge a batch of ad records into `jobs`. Replaces the old wipe-and-replace.

    Uses PG INSERT ... ON CONFLICT (id) DO UPDATE for atomicity. The DO UPDATE set reuses
    the existing merge intent (richer description, union sources, earliest date) but is
    expressed in SQL; first_seen_at is excluded from the update (insert-only) and
    last_seen_at is bumped to now(). NEVER touches job_actions, so human status survives.

    Returns {inserted, updated} counts (best-effort: counts rows seen vs already present).
    """
    if not records:
        return {"inserted": 0, "updated": 0}

    now = datetime.now(timezone.utc)
    inserted = updated = 0
    with session_scope() as session:
        # Pull the existing ad data for the incoming ids so we can run the canonical
        # merge in Python (one round-trip, then one upsert each).
        ids = [r["id"] for r in records]
        existing = {j.id: _job_to_dict(j, None) for j in session.scalars(select(Job).where(Job.id.in_(ids)))}

        for rec in records:
            if rec["id"] in existing:
                merged = store.merge_job(existing[rec["id"]], rec)  # richer desc, union src, earliest date
                updated += 1
            else:
                merged = rec
                inserted += 1

            payload = _ad_columns(merged)
            payload["id"] = rec["id"]
            payload["first_seen_at"] = now  # only used on INSERT path
            payload["last_seen_at"] = now

            stmt = pg_insert(Job).values(**payload)
            # Values are already merged, so DO UPDATE just writes them. first_seen_at is
            # deliberately NOT in the SET (insert-only); last_seen_at is bumped.
            update_set = {col: getattr(stmt.excluded, col) for col in _JOB_AD_COLUMNS if col in payload}
            update_set["last_seen_at"] = now
            stmt = stmt.on_conflict_do_update(index_elements=[Job.id], set_=update_set)
            session.execute(stmt)
    return {"inserted": inserted, "updated": updated}


def triage_candidates() -> list[dict]:
    """Untriaged, admitted jobs needing a verdict: derived status 'new' and no verdict yet.
    Pre-filtered jobs (skip_reason → derived 'skipped') and already-scored jobs are excluded.
    Returns full records (incl. description) so the runner can build its prompt."""
    return [r for r in list_jobs(status="new") if not r.get("triage_verdict")]


def apply_triage(job_id: str, verdict: str, reason: str | None, triaged_date: str) -> None:
    """Write a triage result onto the jobs (ad) row. Triage is an ingest-side enrichment of
    source data, not a human edit, so it lives on `jobs` — not job_actions. (fit/anti_fit are
    produced by the scorer but not surfaced in the UI, so they aren't persisted.)"""
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        job.triage_verdict = verdict
        job.triage_reason = reason
        job.triaged_date = triaged_date


def patch_action(job_id: str, **fields) -> dict | None:
    """Upsert the job_actions row for a job (lazily create on first edit). Accepts any of
    status / notes / applied_date. Returns the updated flat record, or None if the job_id
    is unknown in `jobs` (404 at the route). Ingest never calls this — humans do."""
    allowed = {"status", "notes", "applied_date"}
    patch = {k: v for k, v in fields.items() if k in allowed and v is not None}
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None
        action = session.get(JobAction, job_id)
        if action is None:
            action = JobAction(job_id=job_id, status="new")
            session.add(action)
        for k, v in patch.items():
            if k == "applied_date" and isinstance(v, str):
                v = date.fromisoformat(v)
            setattr(action, k, v)
        session.flush()
        return _job_to_dict(job, action)


# --- application_notes (G4 surface; table + fns exist now, endpoints can come later) ----

def get_application_notes(job_id: str) -> dict | None:
    with session_scope() as session:
        note = session.get(ApplicationNote, job_id)
        if note is None:
            return None
        return {
            "job_id": note.job_id, "notes": note.notes, "salary": note.salary,
            "links": note.links or [],
        }


def create_application_notes(job_id: str, salary: str | None = None, links: list[str] | None = None) -> dict | None:
    """Create the application_notes row; copy-once seed `notes` from job_actions.notes if
    the new row's notes would otherwise be empty. No ongoing sync after this point."""
    with session_scope() as session:
        if session.get(Job, job_id) is None:
            return None
        existing = session.get(ApplicationNote, job_id)
        if existing is not None:
            return get_application_notes(job_id)
        action = session.get(JobAction, job_id)
        seeded = action.notes if action else None
        note = ApplicationNote(job_id=job_id, notes=seeded, salary=salary, links=links)
        session.add(note)
        session.flush()
        return {"job_id": note.job_id, "notes": note.notes, "salary": note.salary, "links": note.links or []}
