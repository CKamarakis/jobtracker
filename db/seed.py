"""db/seed.py — one-off: load the existing JSONL pool into Postgres.

Bridges the file era → the DB era. Reads data/jobs.jsonl with the same loader ingest
uses, upserts the ad data into `jobs` (so it doubles as the first real exercise of
upsert_jobs), and carries any non-`new` human status into a `job_actions` row so prior
shortlisted/applied work isn't lost. Idempotent — upsert means it's safe to re-run.

Run:  ./py.ps1 db/seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ingest"))

import store  # noqa: E402

from db import repository as repo  # noqa: E402

JOBS_PATH = REPO_ROOT / "data" / "jobs.jsonl"


def seed() -> None:
    records = list(store.load_jobs(JOBS_PATH).values())
    if not records:
        print(f"No records at {JOBS_PATH} — nothing to seed.")
        return

    # 1) ad data → jobs (upsert reuses merge rules; safe to re-run).
    counts = repo.upsert_jobs(records)

    # 2) carry forward human status only. A pre-filtered job has status 'skipped' in the
    #    JSONL but no real human decision — it's reconstructed from skip_reason on read, so
    #    don't create a job_actions row for it. Only seed genuine human statuses.
    human = 0
    for rec in records:
        status = rec.get("status")
        if status in ("shortlisted", "applied") or (status == "skipped" and not rec.get("skip_reason")):
            repo.patch_action(
                rec["id"], status=status, notes=rec.get("notes"),
                applied_date=rec.get("applied_date"),
            )
            human += 1

    print(
        f"Seeded {len(records)} records "
        f"({counts['inserted']} inserted, {counts['updated']} updated), "
        f"{human} human status rows carried forward."
    )


if __name__ == "__main__":
    seed()
