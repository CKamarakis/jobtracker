"""tests/test_filters.py — pins the deterministic pre-triage gates in ingest/filters.py.

Why these matter (mirrors test_store.py's logic): filters.py is the LLM-free stage
that rejects unambiguous non-fits BEFORE we spend triage tokens (and, for LinkedIn
leads, a web-search + fetch). A one-character edit to those regexes fails SILENTLY —
it either leaks junk to the LLM (cost) or, far worse, eats a real `strong fit`
(lost recall). Today the only thing catching that is the eval: slow, LLM-driven,
costs tokens. These tests make a regression loud and free at commit time.

The two load-bearing design rules from filters.py we lock down here:
  1. RECALL OVER PRECISION — borderline / leadership titles MUST survive to triage.
  2. German compounds defeat \b — STEM (substring) hits must fire inside compounds.

Run:  python -m pytest tests/ -q
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

# ingest/ has no package; add it to the path so `import filters` resolves (matches run.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

import filters  # noqa: E402


# --------------------------------------------------------------------------- #
# title_rejected — the WORD-bounded denylist (real English / short words)
# --------------------------------------------------------------------------- #

class TestTitleDenyWord:
    @pytest.mark.parametrize("title", [
        "Junior Product Manager",
        "Software Engineer",
        "Senior Backend Developer",
        "DevOps Engineer",
        "SRE",
        "QA Lead",
        "Data Scientist",
        "Account Executive",
        "Sales Manager",
        "Technical Recruiter",
        "Business Development Representative",
        "Country Manager DACH",
        "Payroll Specialist",
        "People & Culture Lead",
        "Customer Success Manager",
        "SEO Manager",
        "Project Manager",
        "Graphic Designer",
        "Working Student Marketing",
    ])
    def test_word_denylist_rejects(self, title):
        assert filters.title_rejected(title) is not None

    def test_word_boundary_does_not_overmatch(self):
        # "qa" is \b-bounded precisely so it does NOT fire inside another word.
        assert filters.title_rejected("Head of Acqua Product") is None


# --------------------------------------------------------------------------- #
# title_rejected — the STEM (substring) denylist: German compounds defeat \b
# --------------------------------------------------------------------------- #

class TestTitleDenyStem:
    @pytest.mark.parametrize("title", [
        "Pflichtpraktikum Produktmanagement",      # praktik inside a compound
        "Werkstudent Data",
        "Lohnbuchhaltung",                         # buchhalt inside a compound
        "Buchhalter",
        "Frontend-EntwicklerIn",                   # entwickler + inflection
        "Bauprojektmanager",                       # projektmanage inside a compound
        "Nachtragsmanager",
        "Qualitätsmanagement",                     # umlaut variant
        "Qualitaetsmanager",                       # ae variant
        "Energieberater",                          # berater inside a compound
        "Vertriebscontroller",                     # controller inside a compound
        "Grafikdesign",
        "Außendienst",
        "Servicetechniker",
    ])
    def test_stem_denylist_rejects_inside_compounds(self, title):
        assert filters.title_rejected(title) is not None

    def test_entwicklung_is_not_denied(self):
        # Deliberate: "Produktentwicklung" can front a real lead → must survive.
        assert filters.title_rejected("Head of Produktentwicklung") is None


# --------------------------------------------------------------------------- #
# title_rejected — RECALL: borderline / leadership titles MUST reach triage
# --------------------------------------------------------------------------- #

class TestTitleSurvivesToTriage:
    @pytest.mark.parametrize("title", [
        "Head of Product",
        "VP Product",
        "CPO",
        "Chief Product Officer",
        "Director of Product",
        "Senior Product Manager",
        "Principal Product Manager",
        "Founding Product Manager",
        "Group Product Manager",
        "Head of Product & Engineering",   # coupled lead — 'engineers?' must NOT bite
        "General Manager",                 # bare GM survives (only 'country manager' denied)
    ])
    def test_leadership_titles_pass(self, title):
        assert filters.title_rejected(title) is None, f"recall regression: {title!r} was rejected"


# --------------------------------------------------------------------------- #
# title_rejected — SAP: deny only consultant/specialist/dev co-occurrence
# --------------------------------------------------------------------------- #

class TestSapGate:
    @pytest.mark.parametrize("title", [
        "SAP Consultant",
        "SAP ABAP Developer",
        "SAP Basis Administrator",
        "Inhouse SAP Berater",
    ])
    def test_sap_with_specialist_marker_rejected(self, title):
        assert filters.title_rejected(title) is not None

    def test_sap_product_role_survives(self):
        # A product role that merely touches SAP must reach triage.
        assert filters.title_rejected("Product Manager, SAP integrations") is None


# --------------------------------------------------------------------------- #
# is_stale — date-boundary logic; unknown/unparseable → keep (recall)
# --------------------------------------------------------------------------- #

class TestIsStale:
    TODAY = date(2026, 6, 16)

    def test_old_post_is_stale(self):
        assert filters.is_stale("2026-04-01", self.TODAY) is True

    def test_recent_post_is_fresh(self):
        assert filters.is_stale("2026-06-10", self.TODAY) is False

    def test_exactly_at_boundary_is_not_stale(self):
        # > max_age_days, not >=: 30 days old is kept, 31 is cut.
        thirty = "2026-05-17"   # 30 days before 2026-06-16
        assert filters.is_stale(thirty, self.TODAY) is False

    def test_one_past_boundary_is_stale(self):
        assert filters.is_stale("2026-05-16", self.TODAY) is True  # 31 days

    @pytest.mark.parametrize("bad", ["", "not-a-date", "2026-13-01"])
    def test_missing_or_unparseable_is_kept(self, bad):
        assert filters.is_stale(bad, self.TODAY) is False


# --------------------------------------------------------------------------- #
# is_expired — freshness re-aging; posted_ts precise path + date fallback
# --------------------------------------------------------------------------- #

class TestIsExpired:
    NOW = 1_700_000_000.0  # arbitrary fixed "now"

    def test_posted_ts_within_window_is_fresh(self):
        rec = {"posted_ts": self.NOW - 3600}  # 1h ago, default window 28h
        assert filters.is_expired(rec, self.NOW) is False

    def test_posted_ts_past_window_is_expired(self):
        rec = {"posted_ts": self.NOW - 30 * 3600}  # 30h ago
        assert filters.is_expired(rec, self.NOW) is True

    def test_date_fallback_uses_latest_possible_instant(self):
        # A date-only legacy record is expired ONLY when even a 23:59 post would exceed
        # the window — a borderline 'yesterday' is kept, not guessed stale.
        from datetime import datetime, timezone
        today = datetime.fromtimestamp(self.NOW, tz=timezone.utc).date()
        rec = {"posted_date": today.isoformat()}
        assert filters.is_expired(rec, self.NOW) is False

    def test_old_date_fallback_is_expired(self):
        rec = {"posted_date": "2020-01-01"}
        assert filters.is_expired(rec, self.NOW) is True

    def test_missing_both_fields_never_expires(self):
        assert filters.is_expired({}, self.NOW) is False

    def test_unparseable_date_never_expires(self):
        assert filters.is_expired({"posted_date": "garbage"}, self.NOW) is False


# --------------------------------------------------------------------------- #
# prefilter — composition: title gate fires before the date gate
# --------------------------------------------------------------------------- #

class TestPrefilter:
    TODAY = date(2026, 6, 16)

    def test_passes_a_fresh_leadership_role(self):
        rec = {"title": "Head of Product", "posted_date": "2026-06-15"}
        assert filters.prefilter(rec, self.TODAY) is None

    def test_title_rejection_wins_over_fresh_date(self):
        rec = {"title": "Junior Developer", "posted_date": "2026-06-15"}
        reason = filters.prefilter(rec, self.TODAY)
        assert reason is not None and "denylist" in reason

    def test_stale_fresh_title_rejected_on_date(self):
        rec = {"title": "Head of Product", "posted_date": "2026-01-01"}
        reason = filters.prefilter(rec, self.TODAY)
        assert reason is not None and "stale" in reason
