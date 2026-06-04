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
import urllib.request
from datetime import date, timezone, datetime

from store import job_key

API_URL = "https://www.arbeitnow.com/api/job-board-api"
SOURCE = "arbeitnow"
USER_AGENT = "jobhunt-ingest/1.0 (personal job search; contact c.kamarakis@gmail.com)"

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


def fetch(max_pages: int = 5) -> list[dict]:
    """Fetch up to max_pages of the board and map to job records.

    max_pages bounds the volume for a polite daily pull (the API returns ~100/page).
    Stops early when a page is empty. Returns records WITH the `new` status; the
    orchestrator (run.py) handles dedup/merge against existing jobs.jsonl.
    """
    records: list[dict] = []
    for page in range(1, max_pages + 1):
        payload = _get(f"{API_URL}?page={page}")
        items = payload.get("data", [])
        if not items:
            break
        records.extend(_to_record(it) for it in items)
    return records
