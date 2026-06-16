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
from datetime import date, datetime, timezone

# Ads older than this are cut even when a search specifies no date range — stale
# posts are usually filled or ghost listings. Tune in one place.
MAX_AGE_DAYS = 30

# Permissive denylist of unambiguous non-fits for a senior product/eng leader.
# Seniority floor + clearly-off role FAMILIES only — never a sector. (e.g. we deny
# "Pflegefachkraft" the role, but not "...Gesundheitswesen" the domain, which can
# front a real ops/product fit.) When in doubt, it is NOT here — let triage decide.
#
# TWO regexes by design, because German compounds defeat \b:
#  - STEM (substring, no boundaries): German stems that COMPOUND or inflect, where a
#    word boundary silently fails. "praktik" must die inside "Pflicht­praktikum"
#    (the internship signal is decisive regardless of the field that follows it);
#    "buchhalt" must match "Buchhalter"/"Lohnbuchhaltung"; "entwickler" must match
#    "EntwicklerIn". These stems are distinctive enough to carry ~no false-positive
#    risk. Deliberately NOT "entwicklung" — "Produktentwicklung" can front a real lead.
#  - WORD (\b-bounded): real English/short words that WOULD over-match as substrings
#    (e.g. "qa" inside another word). Note "engineers?" not "engineering": this cuts
#    IC titles ("Software/Staff/Laravel Engineer") but lets a coupled
#    "Head of Product & Engineering" (a real strong fit) through to triage.
_TITLE_DENY_STEM = re.compile(
    r"(praktik|werkstudent|ausbildung|minijob|"
    # accounting / finance / tax / payroll clerks (German stems compound & inflect)
    r"buchhalt|steuerberat|steuerfachangestellte|entgelt|lohnabrechn|"
    # engineering / creative IC stems (grafik catches 'Grafikdesign'; designer keeps 'Head of Design')
    r"entwickler|systemelektroniker|grafik|designer|"
    # project / claim / quality management (NOT 'Produktmanager' — distinct word);
    # compound-safe so 'Bauprojektmanager'/'Nachtragsmanager'/'Qualitätsmanagement' die
    r"projektmanage|projektleit|nachtrag|claimmanage|qualit(ä|ae)tsmanage|"
    # marketing / analyst / consulting / controlling ICs (berater catches 'Energieberater';
    # controller as a stem catches 'Vertriebscontroller' that \bcontroller\b would miss)
    r"marketing|analyst|berater|controller|controlling|pr(ü|ue)fungsassist|"
    # skilled-trade / field-service / safety / environment
    r"techniker|mechatronik|anlagenf(ü|ue)hr|au(ß|ss)endienst|baustellen|bau(ü|ue)berwach|"
    r"arbeitssicherheit|sicherheitsingenieur|umwelttechnik|grundwasser|altlasten|"
    # retail / property / callcenter / clerical (callcent as a stem catches 'Callcenter')
    r"filialleit|verwalter|kundenservice|callcent|datenerfass|b(ü|ue)rokau|testkunde)",
    re.IGNORECASE,
)
_TITLE_DENY_WORD = re.compile(
    r"\b("
    # seniority floor / non-permanent
    r"junior|jr|intern|internship|trainee|apprentice|graduate|"
    r"working\s+student|teilzeit|studentische|"
    # engineering / IT individual-contributor (NOT 'engineering' the org → leadership)
    r"engineers?|developers?|devops|sre|qa|quality\s+assurance|tester|"
    r"administrator|sysadmin|data\s+scientist|"
    # off-role-family: sales / recruiting / business development / regional GM
    r"sales|account\s+executive|account\s+manager|sdr|bdr|recruiter|recruiting|"
    r"paralegal|business\s+development|country\s+manager|"
    # off-role-family: accounting / finance / tax / payroll clerks
    r"accountant|bookkeeper|kreditoren|kreditanalyst|revenue|"
    r"wirtschaftspr(ü|ue)fer|payroll|human\s+resources|hr[\s-]?manager|"
    # off-role-family: people / HR
    r"people\s+operations|people\s+manage|people\s*&\s*culture|"
    # off-role-family: marketing / customer-success / project-mgmt individual-contributor
    r"social\s+media|customer\s+success|customer\s+support|crm\s+manager|"
    r"seo|tiktok|influencer|creator|project\s+manager|store\s+manager|"
    r"call\s+agent|consultant|supporter|"
    # off-role-family: skilled-trade / care / manual
    r"pflege|pflegefachkraft|elektroniker|monteur|mechaniker|reinigung|"
    r"verk(ä|ae)ufer|lagerist|koch|servicetechnik|hse|ehs|"
    # off-role-family: creative IC (a 'Head of Design' lead survives — no bare 'designer')
    r"graphic\s+designer|mediengestalter|texter|copywriter"
    r")\b",
    re.IGNORECASE,
)

# SAP roles on this board are overwhelmingly consultant/specialist ICs — a non-fit.
# But we DON'T blanket-deny "sap": a "Product Manager, SAP integrations" should reach
# triage. So reject only when SAP co-occurs with a consultant/specialist/dev marker.
_SAP_RE = re.compile(r"\bsap\b", re.IGNORECASE)
_SAP_COTERM_RE = re.compile(
    r"\b(consultant|consulting|berater|spezialist|specialist|entwickler|developer|"
    r"administrator|basis|abap|inhouse)\b",
    re.IGNORECASE,
)


def title_rejected(title: str) -> str | None:
    """Return a skip reason if the title is an unambiguous non-fit, else None.

    Exposed on its own so a lead-only source (LinkedIn) can call it BEFORE the
    expensive enrichment fetch — that pre-enrichment gate is where this saves the
    most resources, not just triage tokens.
    """
    t = title or ""
    m = _TITLE_DENY_WORD.search(t) or _TITLE_DENY_STEM.search(t)
    if m:
        return f"title denylist: '{m.group(0).lower().strip()}'"
    if _SAP_RE.search(t) and _SAP_COTERM_RE.search(t):
        return "title denylist: 'sap' specialist/consultant"
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


# ── Freshness re-aging ────────────────────────────────────────────────────────
# DISTINCT from the prefilter `is_stale` gate above. That one runs ONCE, at insert,
# on day granularity (30d catch-all). This runs on EVERY pool member EVERY run, on
# hour granularity, to close the gap that bit us: the fetch window only gates ENTRY,
# so once admitted a job never re-aged and the pool grew unbounded with stale ads.
# Default mirrors arbeitnow's fetch cutoff (DEFAULT_MAX_AGE_HOURS) — the active pool
# should hold only what a fresh fetch would still admit. Widen for a catch-up run.
DEFAULT_FRESH_HOURS = 28


def is_expired(rec: dict, now_ts: float, fresh_hours: float = DEFAULT_FRESH_HOURS) -> bool:
    """True if the job has aged past the freshness window (should leave the active pool).

    Precise path: posted_ts (Unix epoch) vs now — hour-accurate.
    Fallback: legacy records predating posted_ts have only a date. Expire them ONLY when
    unambiguously past the window — i.e. even a 23:59 post on that date would exceed it —
    so a borderline 'yesterday' record is kept, not guessed stale (recall over precision).
    Missing both fields → never expire (don't drop on absent data)."""
    window_s = fresh_hours * 3600
    ts = rec.get("posted_ts")
    if isinstance(ts, (int, float)):
        return (now_ts - ts) > window_s
    pd = rec.get("posted_date")
    if pd:
        try:
            d = date.fromisoformat(pd)
        except ValueError:
            return False
        latest_possible = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc).timestamp()
        return (now_ts - latest_possible) > window_s
    return False
