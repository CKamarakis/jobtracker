"""ingest/adzuna.py — fetch jobs from the Adzuna aggregator API.

Free dev tier (app_id + app_key from https://developer.adzuna.com/). Adzuna is a
broad aggregator, NOT a curated ATS board like Arbeitnow — an unfiltered country=de
pull returns the entire German labour market. So we drive it with phrase queries from
the title taxonomy and let triage do the real judging. Deterministic mapping only:
no LLM, no judgment.

GOTCHA — descriptions are truncated. The search endpoint returns a ~500-char snippet
ending in '…', never the full ad. Triage on an Adzuna-only job is therefore weaker.
This is fine by design: Adzuna is a *discovery* net. When the same role also lands via
Arbeitnow/ATS, store.merge_job keeps the longer description automatically; otherwise a
later fetch-enrich pass (follow redirect_url → canonical ad) can backfill full text.

Auth/keys come from .env (ADZUNA_APP_ID / ADZUNA_APP_KEY). If they're missing, fetch()
raises — run.py catches per-source errors, so a missing key fails Adzuna alone without
aborting the other sources.

API: GET https://api.adzuna.com/v1/api/jobs/de/search/{page}?app_id=..&app_key=..&what_phrase=..
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from arbeitnow import html_to_text  # Adzuna snippets can carry HTML entities; reuse the cleaner.
from store import job_key

API_BASE = "https://api.adzuna.com/v1/api/jobs"
COUNTRY = "de"
SOURCE = "adzuna"
USER_AGENT = "jobhunt-ingest/1.0 (personal job search; contact c.kamarakis@gmail.com)"

# Phrase queries derived from the title taxonomy in profile/parameters.md. Each is an
# exact-phrase search (what_phrase). Kept tight on purpose — broad terms drag in the
# whole market. Add/trim here to widen or narrow the net.
QUERIES = [
    "head of product",
    "director of product",
    "product manager",
    "product lead",
    "principal product manager",
]

# Tuning knobs — bounded for a polite daily pull well under the free tier (~250 calls/day,
# 25/min). len(QUERIES) * MAX_PAGES calls per run.
MAX_DAYS_OLD = 1         # freshness window (API-side). Day granularity is the tightest
                         # Adzuna offers — ~last 24h. Raise to 3-7 for a wider catch-up pull.
RESULTS_PER_PAGE = 50    # API maximum.
MAX_PAGES = 2            # pages per phrase.

# No remote flag in the Adzuna schema — infer it from the text so the triage location
# filter has a signal. Conservative: only obvious markers.
_REMOTE_MARKERS = ("remote", "home office", "homeoffice", "remote-first", "fully remote")


def _creds() -> tuple[str, str]:
    """Read Adzuna keys from the environment, loading .env if present. Raises if unset."""
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        except ModuleNotFoundError:
            pass
        app_id = os.environ.get("ADZUNA_APP_ID")
        app_key = os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set (see .env).")
    return app_id, app_key


def _get(page: int, what_phrase: str, app_id: str, app_key: str, max_days_old: int = MAX_DAYS_OLD) -> dict:
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": RESULTS_PER_PAGE,
        "what_phrase": what_phrase,
        "max_days_old": max_days_old,
        "sort_by": "date",
        # NOTE: no `where`. country=de already scopes nationally; `where=Germany` matches
        # the English string against German location text and returns zero.
    }
    url = f"{API_BASE}/{COUNTRY}/search/{page}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _to_record(item: dict) -> dict:
    company = (item.get("company") or {}).get("display_name", "")
    title = item.get("title", "")
    location = (item.get("location") or {}).get("display_name", "")
    description = html_to_text(item.get("description", ""))

    posted = ""
    posted_ts = None
    created = item.get("created")  # ISO 8601, e.g. '2026-05-29T11:58:20Z'
    if isinstance(created, str) and created:
        posted = created[:10]  # date portion is already YYYY-MM-DD
        try:  # keep the epoch too — freshness re-aging needs hour precision
            posted_ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
        except ValueError:
            posted_ts = None

    blob = f"{title}\n{description}".lower()
    remote = any(m in blob for m in _REMOTE_MARKERS)

    return {
        "id": job_key(company, title, location),
        "source": [SOURCE],
        "company": company,
        "title": title,
        "location": location,
        "remote": remote,
        # redirect_url is Adzuna's landing/redirect, not the canonical ATS link — same
        # situation as Arbeitnow. Store it as url; leave ats_url for later enrichment.
        "url": item.get("redirect_url", ""),
        "ats_url": "",
        "description": description,
        "posted_date": posted,
        "posted_ts": posted_ts,  # Unix epoch (post time); None if unparseable
        "status": "new",
    }


def fetch(max_days_old: int = MAX_DAYS_OLD) -> list[dict]:
    """Run each phrase query, paginate, and map to job records.

    Dedups within this pull by Adzuna's own job id (phrases overlap — a 'product lead'
    can also match 'head of product'). Returns records with `new` status; run.py owns
    cross-source dedup/merge against jobs.jsonl. One bad query is logged and skipped so a
    single failure doesn't lose the rest of the pull.

    max_days_old: API-side freshness window in days (the search-duration knob the app
    exposes — 1 / 3 / 7). Day granularity is the tightest Adzuna offers.
    """
    app_id, app_key = _creds()
    seen_ids: set[str] = set()
    records: list[dict] = []

    for phrase in QUERIES:
        for page in range(1, MAX_PAGES + 1):
            try:
                payload = _get(page, phrase, app_id, app_key, max_days_old)
            except Exception as e:
                print(f"    [adzuna] query {phrase!r} page {page} failed: {e}")
                break
            items = payload.get("results", [])
            if not items:
                break
            for it in items:
                aid = str(it.get("id", ""))
                if aid and aid in seen_ids:
                    continue
                seen_ids.add(aid)
                records.append(_to_record(it))

    return records
