"""ingest/store.py — dedup key + JSONL read/write/merge for data/jobs.jsonl.

No database: storage is one JSON object per line. The dedup key is a stable hash
of company + normalized title + location, so the SAME ad from a different source or
a later daily run collapses onto one record instead of duplicating. Merge rules
(CLAUDE.md) preserve human work: an already-triaged/applied job never resets to `new`.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


# German job titles carry gender tags — (m/w/d), (w/m/d), (m/f/d), (all genders), … —
# and each board formats/includes them differently. They are NOT part of the role, so
# strip them before hashing or the same job keys differently across sources.
_GENDER_RE = re.compile(
    r"\(\s*[mwfdxn](?:\s*[/\\]\s*[mwfdxn]){1,3}\s*\)"          # (m/w/d), (w/m/d), (m/f/x)
    r"|\b[mwfdxn](?:\s*[/\\]\s*[mwfdxn]){2,3}\b"               # bare m/w/d
    r"|\(\s*(?:all\s+genders|divers|gender[\s-]*neutral|gn)\s*\)",
    re.IGNORECASE,
)
# Cross-source spelling drift in the same token. Keep tiny and high-confidence.
_TITLE_ALIASES = {"sr": "senior", "jr": "junior"}


def normalize_title(title: str) -> str:
    """Aggressively canonicalize a title so the SAME role from different boards collapses
    to one key. Strip gender tags, drop punctuation, fold known abbreviations, collapse
    whitespace. Intentionally lossy — recall (one record per role) beats keeping decorations."""
    t = title.lower()
    t = _GENDER_RE.sub(" ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    tokens = (_TITLE_ALIASES.get(w, w) for w in t.split())
    return " ".join(tokens).strip()


def job_key(company: str, title: str, location: str) -> str:
    """Stable dedup id = company + normalized title, deliberately WITHOUT location.

    Location is excluded because the same role renders its city many ways across sources
    ('Berlin' / 'Berlin, Germany' / 'Berlin, Berlin, Almanya' / 'München' vs 'Munich'),
    which fragmented the key and let a judged role re-enter as `new` from a second board.
    Tradeoff: a company posting the SAME title in two genuinely different cities now
    collapses to one record — rare for senior roles at <2000-person firms, and acceptable
    for a Berlin/remote-focused search. `location` stays a stored field (used by merge and
    the triage location filter); we just don't key on it. Truncated SHA-1 is ample here.
    The `location` arg is kept for call-site compatibility but ignored.
    """
    raw = f"{company.lower().strip()}|{normalize_title(title)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_jobs(path: Path) -> dict[str, dict]:
    """Read jobs.jsonl into a dict keyed by id. Empty/missing file → empty dict."""
    if not path.exists():
        return {}
    jobs: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        jobs[rec["id"]] = rec
    return jobs


def save_jobs(path: Path, jobs: dict[str, dict]) -> None:
    """Write the dict back to JSONL, one record per line, sorted by id for stable diffs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(jobs[k], ensure_ascii=False)
        for k in sorted(jobs)
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def merge_job(existing: dict, incoming: dict) -> dict:
    """Combine a re-seen ad with its stored record without losing human progress.

    - description: keep the richer (longer) one — LinkedIn leads arrive thin, ATS pages thick.
    - source: union the lists.
    - posted_date: keep the earliest non-empty.
    - status: ALWAYS keep the existing status — a triaged/applied job must not reset to `new`.
    - ats_url / other fields: backfill only if existing is missing it.
    - alt_locations: since the key is location-free, a collapse can span cities. Keep the
      primary in `location` and stash the other distinct cities here — that's the
      "also hiring in X / abroad" signal Chris wanted to retain. Field is omitted entirely
      for records that never collapsed across locations, so single-city jobs stay clean.
    """
    merged = dict(existing)

    if len(incoming.get("description", "")) > len(existing.get("description", "")):
        merged["description"] = incoming["description"]

    merged["source"] = sorted(set(existing.get("source", []) + incoming.get("source", [])))

    dates = [d for d in (existing.get("posted_date"), incoming.get("posted_date")) if d]
    if dates:
        merged["posted_date"] = min(dates)

    # Backfill empty scalar fields from the incoming record (never overwrite a real value).
    for field in ("location", "remote", "url", "ats_url", "title", "company"):
        if not existing.get(field) and incoming.get(field):
            merged[field] = incoming[field]

    # Preserve distinct non-primary cities seen across the collapse (incl. any already
    # accumulated on either record). Excludes the primary location and empties.
    primary = merged.get("location", "")
    seen = set(existing.get("alt_locations", [])) | set(incoming.get("alt_locations", []))
    seen |= {existing.get("location", ""), incoming.get("location", "")}
    alts = sorted(loc for loc in seen if loc and loc != primary)
    if alts:
        merged["alt_locations"] = alts

    # status is intentionally NOT touched — preserve existing.
    return merged
