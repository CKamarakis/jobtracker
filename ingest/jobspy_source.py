"""ingest/jobspy_source.py — source adapter over the JobSpy library.

JobSpy (pip: python-jobspy, MIT) scrapes LinkedIn / Indeed / Glassdoor / Google /
ZipRecruiter concurrently and returns a pandas DataFrame. We use it instead of
hand-rolling a per-board scraper: it maintains the access layer (the cat-and-mouse
with each board's anti-bot), gives full descriptions and date_posted, and exposes
`hours_old` for the recency window we actually want.

This module is the deterministic mapping layer only: call scrape_jobs(), normalize
each row into our record schema, hand back to the dedup/merge pipeline (store.py).

Run directly for a quick summary:
    python ingest/jobspy_source.py
"""

from __future__ import annotations

import math

import pandas as pd
from jobspy import scrape_jobs

from store import job_key

# Boards in rough order of reliability for our use (LinkedIn/Google rarely block;
# Indeed/Glassdoor share a Cloudflare parent and are flakier — added but expendable).
DEFAULT_SITES = ["linkedin"]
DEFAULT_TERMS = ["product manager", "head of product"]


def _clean(v) -> str:
    """pandas fills missing cells with NaN (a float). Coerce anything empty to ''."""
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


def _is_remote(v) -> bool:
    if v is True:
        return True
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return False


def _posted(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v):
        return ""
    if hasattr(v, "date"):
        return v.date().isoformat()
    return _clean(v)


def _to_record(row: dict, site: str) -> dict:
    company = _clean(row.get("company"))
    title = _clean(row.get("title"))
    location = _clean(row.get("location"))
    return {
        "id": job_key(company, title, location),
        "source": [f"jobspy:{site}"],
        "company": company,
        "title": title,
        "location": location,
        "remote": _is_remote(row.get("is_remote")),
        "url": _clean(row.get("job_url")) or _clean(row.get("job_url_direct")),
        "ats_url": _clean(row.get("job_url_direct")),
        "description": _clean(row.get("description")),
        "posted_date": _posted(row.get("date_posted")),
        "status": "new",
    }


def fetch(
    sites: list[str] | None = None,
    terms: list[str] | None = None,
    location: str = "Berlin, Germany",
    results_wanted: int = 40,
) -> list[dict]:
    """Pull jobs for each search term across each board and map to records.

    NOTE: pinned to the JobSpy build installable under Python 3.14 (1.1.13), which has
    no `hours_old` recency filter or description toggle — recency must be filtered
    client-side on `posted_date`. The newer JobSpy (richer API) needs Python 3.12/3.13
    wheels. dedup/merge happens in run.py.
    """
    sites = sites or DEFAULT_SITES
    terms = terms or DEFAULT_TERMS
    records: list[dict] = []
    for term in terms:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                location=location,
                results_wanted=results_wanted,
                country_indeed="germany",
            )
        except Exception as e:
            print(f"  [{term}] scrape FAILED: {e}")
            continue
        if df is None or df.empty:
            print(f"  [{term}] 0 rows")
            continue
        print(f"  [{term}] {len(df)} rows | columns: {list(df.columns)}")
        for row in df.to_dict("records"):
            records.append(_to_record(row, _clean(row.get("site")) or "?"))
    return records


if __name__ == "__main__":
    recs = fetch()
    print(f"\nTotal records mapped: {len(recs)}")
    by_source: dict[str, int] = {}
    for r in recs:
        by_source[r["source"][0]] = by_source.get(r["source"][0], 0) + 1
    print("By source:", by_source)
    print("\nSample (first 25):")
    for r in recs[:25]:
        rem = " [remote]" if r["remote"] else ""
        desc = f"  desc:{len(r['description'])}c" if r["description"] else "  desc:-"
        print(f"  - {r['title']}  @  {r['company']}  ({r['location']}){rem}  {r['posted_date']}{desc}")
