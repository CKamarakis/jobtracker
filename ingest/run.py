"""ingest/run.py — ingestion orchestrator.

Fetches the selected sources for a chosen freshness window and UPSERTS the pool into
Postgres (db.repository). Deterministic and LLM-free by design (CLAUDE.md): it can run
unattended and cannot hallucinate. Add a new source by registering its `fetch()` in SOURCES.

DURABLE POOL (Phase D): each run UPSERTS its results into Postgres (db.repository) —
the pool accumulates and is dedup-merged across runs, never wiped. Human edits live in a
separate table ingest never touches, so a re-fetch can't reset an approved/applied job to
`new`. (The dashboard shows a fresh-window VIEW over this durable pool — see
db.repository.dashboard_jobs — which gives the same clean "last run" feel as the old wipe
without losing anything.) Cross-SOURCE dedup within a single run still happens here first.

Usage:
    python ingest/run.py                      # all sources, 1-day window
    python ingest/run.py --duration 1w        # all sources, 1-week window
    python ingest/run.py --sources arbeitnow  # one source
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import adzuna
import arbeitnow
import filters
import store

REPO_ROOT = Path(__file__).resolve().parent.parent
# run.py is launched as a script (`./py.ps1 ingest/run.py`), so sys.path[0] is ingest/, not
# the repo root — add the root so `db` (the Phase D persistence package) imports cleanly.
sys.path.insert(0, str(REPO_ROOT))
from db import repository as repo  # noqa: E402

# Search-duration knob the app exposes → days. Each source maps it to its own native
# freshness control (arbeitnow: client-side hours cutoff; adzuna: API max_days_old).
DURATION_DAYS = {"1d": 1, "3d": 3, "1w": 7}
DEFAULT_DURATION = "1d"


# Per-source adapters: a uniform (days, fresh_hours) signature over each source's own
# fetch() so run_ingest can call them all the same way. Register a new source here.
def _fetch_arbeitnow(days: int, fresh_hours: float) -> list[dict]:
    return arbeitnow.fetch(max_age_hours=fresh_hours)


def _fetch_adzuna(days: int, fresh_hours: float) -> list[dict]:
    return adzuna.fetch(max_days_old=days)


SOURCES: dict[str, Callable[[int, float], list[dict]]] = {
    "arbeitnow": _fetch_arbeitnow,
    "adzuna": _fetch_adzuna,
}


def available_sources() -> list[str]:
    """Source ids the app/CLI may select (drives the dashboard multiselect)."""
    return sorted(SOURCES)


def run_ingest(
    sources: list[str] | None = None,
    duration: str = DEFAULT_DURATION,
    progress: Callable[[str, str, dict | None], None] | None = None,
) -> dict:
    """Fetch `sources` over the `duration` window and UPSERT them into the durable pool.

    sources:  subset of available_sources(); None/empty → all.
    duration: one of DURATION_DAYS keys ("1d"|"3d"|"1w").
    progress: optional callback(phase, message, counts) for live status (the API runner
              uses it to drive GET /fetch/status). No-op by default.

    Returns a summary dict (pool size + per-source counts). LLM-free — triage is a
    separate stage layered on top by the API.
    """
    def emit(phase: str, message: str, counts: dict | None = None) -> None:
        if progress:
            progress(phase, message, counts)

    selected = [s for s in (sources or available_sources()) if s in SOURCES]
    days = DURATION_DAYS.get(duration, DURATION_DAYS[DEFAULT_DURATION])
    fresh_hours = days * 24 + 4  # small buffer, mirrors arbeitnow's ingest-time slack
    today = datetime.now(timezone.utc).date()

    jobs: dict[str, dict] = {}  # this run's records, cross-SOURCE merged before the upsert
    added = merged = skipped = 0
    per_source: dict[str, int | str] = {}

    for name in selected:
        emit("fetch", f"fetching {name}", {"pool": len(jobs)})
        try:
            fetched = SOURCES[name](days, fresh_hours)
        except Exception as e:  # one bad source shouldn't abort the whole run
            per_source[name] = f"FAILED: {e}"
            emit("fetch", f"{name} failed: {e}", {"pool": len(jobs)})
            continue
        per_source[name] = len(fetched)
        for rec in fetched:
            key = rec["id"]
            if key in jobs:
                # Same role from another source THIS run: merge (richer description, etc.).
                jobs[key] = store.merge_job(jobs[key], rec)
                merged += 1
            else:
                # New record: metadata gate. Rejected jobs are kept, stamped with skip_reason
                # (a jobs column). NB: do NOT set status here — status is human-owned in
                # job_actions; the pre-filter drop is read as 'skipped' via skip_reason.
                reason = filters.prefilter(rec, today=today)
                if reason:
                    rec["skip_reason"] = reason
                    skipped += 1
                jobs[key] = rec
                added += 1

    # Durable upsert into Postgres — merges across runs, never wipes, never touches
    # job_actions (so an approved/applied job re-seen on the board keeps its status).
    emit("write", "upserting pool", {"pool": len(jobs)})
    counts = repo.upsert_jobs(list(jobs.values()))

    summary = {
        "pool": len(jobs),
        "added": added,
        "merged": merged,
        "skipped": skipped,
        "inserted": counts["inserted"],
        "updated": counts["updated"],
        "duration": duration,
        "sources": selected,
        "per_source": per_source,
    }
    return summary


def main(duration: str = DEFAULT_DURATION, sources: list[str] | None = None) -> None:
    summary = run_ingest(sources=sources, duration=duration)
    ps = ", ".join(f"{k}={v}" for k, v in summary["per_source"].items())
    print(
        f"Done ({summary['duration']}, sources: {', '.join(summary['sources'])}). "
        f"This run: +{summary['added']} ({summary['skipped']} pre-filtered), "
        f"{summary['merged']} cross-source merged. "
        f"DB upsert: {summary['inserted']} inserted, {summary['updated']} updated. "
        f"Run size: {summary['pool']} jobs. [{ps}]"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job ingestion (wipe-and-replace pool).")
    parser.add_argument(
        "--duration", choices=list(DURATION_DAYS), default=DEFAULT_DURATION,
        help=f"Search freshness window (default {DEFAULT_DURATION}).",
    )
    parser.add_argument(
        "--sources", nargs="+", choices=available_sources(), default=None,
        help="Sources to fetch (default: all).",
    )
    args = parser.parse_args()
    main(duration=args.duration, sources=args.sources)
