"""tests/test_store.py — pins the dedup key + merge rules in ingest/store.py.

Each test mirrors one sentence from store.py's docstrings. These rules fail SILENTLY
in production (wrong merge → corrupted data/jobs.jsonl, no exception), so the whole
point is to make a clobbered status or a lost source loud at commit time.

Run:  python -m pytest tests/ -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ingest/ has no package; add it to the path so `import store` resolves (matches run.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

import store  # noqa: E402


# --------------------------------------------------------------------------- #
# normalize_title — the same role from any board must canonicalize to one string
# --------------------------------------------------------------------------- #

class TestNormalizeTitle:
    def test_lowercases_and_collapses_whitespace(self):
        assert store.normalize_title("  Senior   Product  Manager ") == "senior product manager"

    @pytest.mark.parametrize("raw", [
        "Senior PM (m/w/d)",
        "Senior PM (w/m/d)",
        "Senior PM (m/f/d)",
        "Senior PM (m/f/x)",
        "Senior PM (all genders)",
        "Senior PM (divers)",
        "Senior PM (gn)",
        "Senior PM m/w/d",  # bare, no parens
    ])
    def test_strips_gender_tags(self, raw):
        assert store.normalize_title(raw) == "senior pm"

    def test_folds_known_abbreviations(self):
        assert store.normalize_title("Sr Product Manager") == "senior product manager"
        assert store.normalize_title("Jr Analyst") == "junior analyst"

    def test_drops_punctuation(self):
        assert store.normalize_title("Product-Manager, Growth") == "product manager growth"

    def test_two_renderings_of_same_role_match(self):
        a = store.normalize_title("Sr. Product Manager (m/w/d)")
        b = store.normalize_title("Senior Product Manager (all genders)")
        assert a == b


# --------------------------------------------------------------------------- #
# job_key — stable, company+title only, location-free
# --------------------------------------------------------------------------- #

class TestJobKey:
    def test_is_stable_across_calls(self):
        assert store.job_key("Acme", "Senior PM", "Berlin") == store.job_key("Acme", "Senior PM", "Berlin")

    def test_ignores_location(self):
        # Same role, different city renderings → one key (the core dedup guarantee).
        assert store.job_key("Acme", "Senior PM", "Berlin") == store.job_key("Acme", "Senior PM", "München")

    def test_ignores_gender_tag_and_case(self):
        assert store.job_key("Acme", "Senior PM (m/w/d)", "Berlin") == store.job_key("acme", "senior pm", "Berlin")

    def test_different_company_differs(self):
        assert store.job_key("Acme", "Senior PM", "Berlin") != store.job_key("Globex", "Senior PM", "Berlin")

    def test_different_role_differs(self):
        assert store.job_key("Acme", "Senior PM", "Berlin") != store.job_key("Acme", "Staff Engineer", "Berlin")


# --------------------------------------------------------------------------- #
# merge_job — combine a re-seen ad without losing human progress
# --------------------------------------------------------------------------- #

class TestMergeJob:
    def _base(self, **over):
        rec = {
            "id": "k", "company": "Acme", "title": "Senior PM", "location": "Berlin",
            "remote": False, "url": "u", "ats_url": "", "description": "short",
            "posted_date": "2026-05-10", "source": ["arbeitnow"], "status": "new",
        }
        rec.update(over)
        return rec

    def test_status_is_never_reset(self):
        existing = self._base(status="applied")
        incoming = self._base(status="new")
        assert store.merge_job(existing, incoming)["status"] == "applied"

    def test_keeps_longer_description(self):
        existing = self._base(description="short")
        incoming = self._base(description="a much longer and richer ATS description")
        assert store.merge_job(existing, incoming)["description"] == incoming["description"]

    def test_does_not_shrink_description(self):
        existing = self._base(description="a much longer and richer ATS description")
        incoming = self._base(description="short")
        assert store.merge_job(existing, incoming)["description"] == existing["description"]

    def test_unions_sources(self):
        existing = self._base(source=["arbeitnow"])
        incoming = self._base(source=["adzuna"])
        assert store.merge_job(existing, incoming)["source"] == ["adzuna", "arbeitnow"]

    def test_keeps_earliest_posted_date(self):
        existing = self._base(posted_date="2026-05-10")
        incoming = self._base(posted_date="2026-05-01")
        assert store.merge_job(existing, incoming)["posted_date"] == "2026-05-01"

    def test_backfills_empty_scalar_but_never_overwrites(self):
        existing = self._base(ats_url="", url="real-url")
        incoming = self._base(ats_url="filled-in", url="other-url")
        merged = store.merge_job(existing, incoming)
        assert merged["ats_url"] == "filled-in"   # was empty → backfilled
        assert merged["url"] == "real-url"         # had a value → preserved

    def test_collects_alt_locations_on_cross_city_collapse(self):
        existing = self._base(location="Berlin")
        incoming = self._base(location="München")
        merged = store.merge_job(existing, incoming)
        assert merged["location"] == "Berlin"          # primary kept
        assert merged["alt_locations"] == ["München"]  # other city retained

    def test_no_alt_locations_field_for_single_city(self):
        existing = self._base(location="Berlin")
        incoming = self._base(location="Berlin")
        assert "alt_locations" not in store.merge_job(existing, incoming)

    def test_does_not_mutate_inputs(self):
        existing = self._base(status="applied", source=["arbeitnow"])
        incoming = self._base(status="new", source=["adzuna"])
        store.merge_job(existing, incoming)
        assert existing["status"] == "applied"
        assert existing["source"] == ["arbeitnow"]


# --------------------------------------------------------------------------- #
# load/save round-trip — JSONL integrity (unicode + empty file)
# --------------------------------------------------------------------------- #

class TestLoadSave:
    def test_round_trip_preserves_records_and_unicode(self, tmp_path):
        path = tmp_path / "jobs.jsonl"
        jobs = {
            "a": {"id": "a", "company": "Acme", "title": "PM", "location": "München"},
            "b": {"id": "b", "company": "Glöbex", "title": "Senior PM", "location": "Berlin"},
        }
        store.save_jobs(path, jobs)
        assert store.load_jobs(path) == jobs

    def test_missing_file_is_empty_dict(self, tmp_path):
        assert store.load_jobs(tmp_path / "nope.jsonl") == {}

    def test_blank_lines_are_skipped(self, tmp_path):
        path = tmp_path / "jobs.jsonl"
        path.write_text('{"id": "a"}\n\n{"id": "b"}\n', encoding="utf-8")
        assert set(store.load_jobs(path)) == {"a", "b"}
