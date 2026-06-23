"""db/models.py — the three ORM tables (Phase D split schema).

Why split (locked decision, ROADMAP "Phase D — DECIDED"): ingest data and human edits
have OPPOSITE lifecycles. Ad rows are re-fetched and overwritten daily; human edits are
sacred. Modeling `status` on `jobs` would let a re-fetch upsert clobber it — so status
lives in `job_actions`, a table ingest has no reason to ever write. That separation is
what makes "durable pool + filtered dashboard" safe.

  jobs               — source-owned ad data; re-fetch UPSERTS (never truncates).
  job_actions        — sacred human edits (status/notes/applied_date); ingest never touches.
  application_notes  — only for jobs actually applied to; notes seeded once from job_actions.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    """Source-owned ad data. Mirrors today's JSONL record. Ingest may overwrite any
    column here on upsert EXCEPT the insert-only `first_seen_at`. `status` is NOT here."""

    __tablename__ = "jobs"

    # Keep the existing 16-char dedup hash (ingest.store.job_key) as PK — don't switch to
    # a serial. It's how cross-source/cross-run dedup already collapses the same ad.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    # source is union-merged across sources → a text[] is closest to today's JSON list.
    source: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
    company: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_locations: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    remote: Mapped[bool | None] = mapped_column(nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # posted_date kept as text to tolerate the JSONL's existing string formats (some null /
    # oddly formatted). posted_ts is the epoch mirror used for the freshness window math.
    posted_date: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    posted_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    triage_verdict: Mapped[str | None] = mapped_column(Text, nullable=True)
    triage_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    triaged_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # first_seen_at: set on INSERT only, never updated (insert-only — see upsert SET list).
    # last_seen_at: bumped on every upsert → "still live on the board" vs "fell off".
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    action: Mapped["JobAction | None"] = relationship(back_populates="job", uselist=False)


class JobAction(Base):
    """Sacred human edits, keyed 1:1 to a job, created lazily on first edit.
    INGEST NEVER WRITES THIS TABLE. Absence of a row ⇒ treat status as `new`."""

    __tablename__ = "job_actions"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(Text, default="new", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[Job] = relationship(back_populates="action")


class ApplicationNote(Base):
    """Only for jobs actually applied to. `notes` is SEEDED ONCE from job_actions.notes
    at row creation (if empty); thereafter the two diverge freely — no ongoing sync."""

    __tablename__ = "application_notes"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary: Mapped[str | None] = mapped_column(Text, nullable=True)  # free-text range, e.g. "90–110k"
    links: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
