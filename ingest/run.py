"""ingest/run.py — daily ingestion orchestrator.

Fetches each source, dedups/merges against data/jobs.jsonl, and writes the pool back.
Deterministic and LLM-free by design (CLAUDE.md): it can run unattended and cannot
hallucinate. Add a new source by importing its `fetch()` into SOURCES below.

Usage:
    python ingest/run.py
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import adzuna
import arbeitnow
import filters
import store

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = REPO_ROOT / "data" / "jobs.jsonl"

# Each source is a zero-arg callable returning a list of job records.
SOURCES = [
    ("arbeitnow", arbeitnow.fetch),
    ("adzuna", adzuna.fetch),
]


def main(fresh_hours: float = filters.DEFAULT_FRESH_HOURS) -> None:
    jobs = store.load_jobs(JOBS_PATH)
    start_count = len(jobs)
    print(f"Loaded {start_count} existing jobs from {JOBS_PATH.relative_to(REPO_ROOT)}")

    today = datetime.now(timezone.utc).date()
    added = merged = skipped = 0
    for name, fetch in SOURCES:
        try:
            fetched = fetch()
        except Exception as e:  # one bad source shouldn't abort the whole run
            print(f"  [{name}] FAILED: {e}")
            continue
        print(f"  [{name}] fetched {len(fetched)} jobs")
        for rec in fetched:
            key = rec["id"]
            if key in jobs:
                # Existing record: merge only; never re-run the gate or reset status.
                jobs[key] = store.merge_job(jobs[key], rec)
                merged += 1
            else:
                # New record: gate it. Rejected jobs are still stored, stamped skipped.
                reason = filters.prefilter(rec, today=today)
                if reason:
                    rec["status"] = "skipped"
                    rec["skip_reason"] = reason
                    skipped += 1
                jobs[key] = rec
                added += 1

    # Re-age the whole pool, not just this run's fetch: expire untriaged jobs past the
    # freshness window. This is the ongoing complement to the fetch-time cutoff — admitted
    # jobs otherwise never age out. Only `new` (untriaged) expires; shortlisted/applied are
    # human-engaged and stay regardless of age, skipped is already terminal.
    now_ts = time.time()
    expired = 0
    for rec in jobs.values():
        if rec.get("status") == "new" and filters.is_expired(rec, now_ts, fresh_hours):
            rec["status"] = "expired"
            rec["skip_reason"] = f"expired: older than {fresh_hours:g}h freshness window"
            expired += 1

    store.save_jobs(JOBS_PATH, jobs)
    print(
        f"\nDone. +{added} new ({skipped} pre-filtered), {merged} re-seen/merged, "
        f"{expired} expired (>{fresh_hours:g}h). Pool: {start_count} -> {len(jobs)} jobs."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily job ingestion + pool re-aging.")
    parser.add_argument(
        "--fresh-hours", type=float, default=filters.DEFAULT_FRESH_HOURS,
        help=f"Active-pool freshness window in hours (default {filters.DEFAULT_FRESH_HOURS:g}). "
             "Raise for a catch-up run that keeps older jobs active.",
    )
    args = parser.parse_args()
    main(fresh_hours=args.fresh_hours)
