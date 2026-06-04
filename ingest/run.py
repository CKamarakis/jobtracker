"""ingest/run.py — daily ingestion orchestrator.

Fetches each source, dedups/merges against data/jobs.jsonl, and writes the pool back.
Deterministic and LLM-free by design (CLAUDE.md): it can run unattended and cannot
hallucinate. Add a new source by importing its `fetch()` into SOURCES below.

Usage:
    python ingest/run.py
"""

from __future__ import annotations

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


def main() -> None:
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

    store.save_jobs(JOBS_PATH, jobs)
    print(
        f"\nDone. +{added} new ({skipped} pre-filtered), {merged} re-seen/merged. "
        f"Pool: {start_count} -> {len(jobs)} jobs."
    )


if __name__ == "__main__":
    main()
