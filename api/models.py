"""api/models.py — Pydantic response models (the API's typed contract).

Why bother typing the responses at all when data_source returns plain dicts?
- These models ARE the contract the React frontend codes against. FastAPI turns
  them into the OpenAPI schema at /docs, so the frontend has a generated, always-
  current spec instead of guessing field names.
- `from_record` keeps the mapping from raw pipeline record → API shape in ONE place.
  When Postgres arrives in Phase D the column names might differ; only this mapping
  changes, not every route.
- Optional/defaulted fields tolerate the real data: not every record is triaged
  (triage_verdict can be null) and older records may lack newer fields.
"""

from __future__ import annotations

from pydantic import BaseModel


class JobSummary(BaseModel):
    """List-view shape: everything the React table needs, minus the heavy description."""
    id: str
    source: list[str] = []
    company: str
    title: str
    location: str | None = None
    remote: bool | None = None
    url: str | None = None
    ats_url: str | None = None
    posted_date: str | None = None
    status: str | None = None
    triage_verdict: str | None = None
    triage_reason: str | None = None  # one-line rationale; surfaced on the rejects list
    notes: str | None = None          # lightweight human note (job_actions.notes)

    @classmethod
    def from_record(cls, rec: dict) -> "JobSummary":
        # `source` is a list in the pipeline but a lone string slips in from some
        # sources — normalize so the frontend always sees a list.
        src = rec.get("source") or []
        if isinstance(src, str):
            src = [src]
        return cls(**{**rec, "source": src})


class JobDetail(JobSummary):
    """Detail-view shape: summary plus the full body and triage trail."""
    description: str | None = None
    triaged_date: str | None = None
    skip_reason: str | None = None
    alt_locations: list[str] | None = None

    @classmethod
    def from_record(cls, rec: dict) -> "JobDetail":
        src = rec.get("source") or []
        if isinstance(src, str):
            src = [src]
        return cls(**{**rec, "source": src})


class MarkdownDoc(BaseModel):
    """A profile / dossier / cover-letter file served as raw markdown text."""
    slug: str
    markdown: str
