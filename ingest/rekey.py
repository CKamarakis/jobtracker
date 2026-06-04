"""ingest/rekey.py — one-time migration: re-hash data/jobs.jsonl under the current key.

Run this ONCE after any change to job_key/normalize_title (e.g. dropping location from
the key, stripping gender tags). It recomputes every record's id with the current scheme
and merges records that now collapse to the same key — so the dedup change applies
retroactively to the stored pool instead of only to future fetches.

Status is preserved across the merge: when two records collapse, the more-advanced status
wins (applied > shortlisted > skipped > new), so a previously judged role is never reset.

Usage:
    python ingest/rekey.py            # writes in place (backs up to jobs.jsonl.bak first)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import store

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = REPO_ROOT / "data" / "jobs.jsonl"

# Most-advanced status wins when two records collapse onto one key.
_STATUS_RANK = {"applied": 3, "shortlisted": 2, "skipped": 1, "new": 0}


def main() -> None:
    old = store.load_jobs(JOBS_PATH)
    if not old:
        print("No jobs to migrate.")
        return

    backup = JOBS_PATH.with_suffix(".jsonl.bak")
    shutil.copyfile(JOBS_PATH, backup)
    print(f"Backed up {len(old)} records to {backup.relative_to(REPO_ROOT)}")

    rekeyed: dict[str, dict] = {}
    collisions = 0
    for rec in old.values():
        new_id = store.job_key(rec.get("company", ""), rec.get("title", ""), rec.get("location", ""))
        rec = dict(rec)
        rec["id"] = new_id
        if new_id in rekeyed:
            collisions += 1
            existing = rekeyed[new_id]
            # Order so the more-advanced status is `existing` — merge_job keeps existing's status.
            a, b = existing, rec
            if _STATUS_RANK.get(b.get("status"), 0) > _STATUS_RANK.get(a.get("status"), 0):
                a, b = b, a
            merged = store.merge_job(a, b)
            merged["id"] = new_id
            rekeyed[new_id] = merged
        else:
            rekeyed[new_id] = rec

    store.save_jobs(JOBS_PATH, rekeyed)
    print(
        f"Re-keyed {len(old)} -> {len(rekeyed)} records "
        f"({collisions} collapsed by the new key). Wrote {JOBS_PATH.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
