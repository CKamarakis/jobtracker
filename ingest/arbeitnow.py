"""ingest/arbeitnow.py — fetch jobs from the Arbeitnow Job Board API.

Free, no API key. Arbeitnow is a Germany/EU-focused board sourced from ATSs
(Greenhouse, Personio, Workable, Lever, Ashby…), so the pool is already mostly
Berlin / German-market — we ingest it broadly and let the triage agent apply
location/size judgment. This module is deterministic mapping only: no LLM, no
filtering decisions that require judgment.

API: GET https://www.arbeitnow.com/api/job-board-api  (paginated via ?page=N)
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from datetime import date, timezone, datetime

from store import job_key

API_URL = "https://www.arbeitnow.com/api/job-board-api"
SOURCE = "arbeitnow"
USER_AGENT = "jobhunt-ingest/1.0 (personal job search; contact c.kamarakis@gmail.com)"

# Freshness window. The board API has NO date param, so we filter client-side on the
# item's `created_at` (a Unix epoch — timezone-absolute, so the comparison has zero tz
# ambiguity). The 4h buffer is a *semantic* hedge, not a tz one: probing the feed shows
# created_at clusters on :00/:15/:30/:45 marks, i.e. it's Arbeitnow's INGEST time, not the
# employer's post time. So we keep a little slack rather than knife-edge a 24h cut.
DEFAULT_MAX_AGE_HOURS = 24 + 4

# Block-level tags → newline so stripped text stays readable; everything else is dropped.
_BLOCK_RE = re.compile(r"</(p|div|li|ul|ol|h[1-6]|tr|table)>|<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    """Arbeitnow descriptions are HTML. Strip to clean text for triage — tags are noise
    to the model and bloat the prompt. Light touch: block tags become line breaks."""
    if not raw:
        return ""
    text = _BLOCK_RE.sub("\n", raw)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # collapse runs of blank lines
    return text.strip()


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _to_record(item: dict) -> dict:
    company = item.get("company_name", "")
    title = item.get("title", "")
    location = item.get("location", "")

    posted = ""
    created = item.get("created_at")
    if isinstance(created, (int, float)):
        posted = datetime.fromtimestamp(created, tz=timezone.utc).date().isoformat()

    return {
        "id": job_key(company, title, location),
        "source": [SOURCE],
        "company": company,
        "title": title,
        "location": location,
        "remote": bool(item.get("remote", False)),
        "url": item.get("url", ""),
        # Arbeitnow's url is a redirect to the real ATS apply page; we don't have the
        # canonical ATS link from the list endpoint, so leave it for later enrichment.
        "ats_url": "",
        "description": html_to_text(item.get("description", "")),
        "posted_date": posted,
        "status": "new",
    }


def fetch(
    max_pages: int = 5,
    max_age_hours: float | None = DEFAULT_MAX_AGE_HOURS,
) -> list[dict]:
    """Fetch up to max_pages of the board and map to job records, newest first.

    max_pages bounds the volume for a polite daily pull (the API returns ~100/page).
    Stops early when a page is empty.

    Freshness (max_age_hours): the feed is sorted newest→oldest (probed: monotonic
    descending bar 1s same-batch jitter), so once a page contains items past the
    cutoff we drop them AND stop paginating — that's the call-saver on quiet days.
    Pass max_age_hours=None to disable and pull the whole window. Items with a
    missing/unparseable created_at are KEPT (recall over precision, matching filters.py).

    Returns records WITH the `new` status; run.py handles dedup/merge against jobs.jsonl.
    """
    cutoff = time.time() - max_age_hours * 3600 if max_age_hours else None
    records: list[dict] = []
    for page in range(1, max_pages + 1):
        payload = _get(f"{API_URL}?page={page}")
        items = payload.get("data", [])
        if not items:
            break
        saw_stale = False
        for it in items:
            created = it.get("created_at")
            if cutoff is not None and isinstance(created, (int, float)) and created < cutoff:
                saw_stale = True  # finish scanning the page (jitter), then stop paging
                continue
            records.append(_to_record(it))
        if saw_stale:
            break
    return records
