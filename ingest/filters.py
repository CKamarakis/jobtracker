"""ingest/filters.py — cheap, deterministic pre-triage gates (date + title).

Why this exists (CLAUDE.md: "hard filters first, reject before scoring"):
triage is the expensive stage — LLM tokens, and for LinkedIn leads a web-search +
fetch per job just to GET the body. Anything we can reject from metadata alone
(title, posted date) should die here, in LLM-free code, before we spend that.

Two deliberate design rules:

1. RECALL OVER PRECISION. Titles are noisy ("Head of Product", "VP Product",
   "CPO", "GM" are all plausible fits). A tight allowlist would silently drop
   strong fits with off-pattern titles — and this code can't reason. So we use a
   permissive DENYLIST of unambiguous misses (seniority floor, wrong role family)
   and let anything borderline through to the LLM, which is the precise stage.

2. NEVER DROP SILENTLY. A rejected job is not discarded — the caller stamps it
   status="skipped" with the returned reason and still stores it. That keeps an
   audit trail AND lets the eval loop measure this filter's false-negative rate
   against the gold set (a cheap filter that eats a labeled `strong fit` is a bug
   we want to catch). Body-dependent filters (>3yr exp, German C1, headcount,
   ≥70% criteria match) stay in triage — they need the description we don't have
   here.
"""

from __future__ import annotations

import re
from datetime import date

# Ads older than this are cut even when a search specifies no date range — stale
# posts are usually filled or ghost listings. Tune in one place.
MAX_AGE_DAYS = 30

# Permissive denylist: word-boundary matches on unambiguous non-fits for a senior
# product/eng leader. Seniority floor + clearly-off role families only. When in
# doubt, it is NOT here — let triage decide. \b avoids substring traps (e.g. "jr"
# inside another word). Add German equivalents because the board is DE-heavy.
_TITLE_DENY = re.compile(
    r"\b("
    r"junior|jr|intern|internship|trainee|apprentice|graduate|"
    r"working\s+student|werkstudent|praktikum|praktikant|ausbildung|"
    r"sales|account\s+executive|sdr|bdr|recruiter|"
    r"accountant|bookkeeper|paralegal"
    r")\b",
    re.IGNORECASE,
)


def title_rejected(title: str) -> str | None:
    """Return a skip reason if the title is an unambiguous non-fit, else None.

    Exposed on its own so a lead-only source (LinkedIn) can call it BEFORE the
    expensive enrichment fetch — that pre-enrichment gate is where this saves the
    most resources, not just triage tokens.
    """
    m = _TITLE_DENY.search(title or "")
    if m:
        return f"title denylist: '{m.group(0).lower()}'"
    return None


def is_stale(posted_date: str, today: date, max_age_days: int = MAX_AGE_DAYS) -> bool:
    """True if posted_date is older than max_age_days. Unknown/empty/unparseable
    date → False (keep it): we don't reject on missing data, that preserves recall."""
    if not posted_date:
        return False
    try:
        posted = date.fromisoformat(posted_date)
    except ValueError:
        return False
    return (today - posted).days > max_age_days


def prefilter(rec: dict, today: date, max_age_days: int = MAX_AGE_DAYS) -> str | None:
    """Metadata-only gate. Return a skip reason string, or None to pass to triage.

    Order: cheapest/most-decisive first. Only fields available without the body.
    """
    reason = title_rejected(rec.get("title", ""))
    if reason:
        return reason
    if is_stale(rec.get("posted_date", ""), today, max_age_days):
        return f"stale: posted {rec.get('posted_date')} (> {max_age_days}d)"
    return None
