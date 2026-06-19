"""api/main.py — FastAPI app: routes + CORS. The web edge of Phase B.

Run from repo root:
    $env:PYTHONUTF8=1
    & "C:\\Users\\Chris\\AppData\\Local\\Programs\\Python\\Python314\\python.exe" -m uvicorn api.main:app --reload

Then open http://127.0.0.1:8000/docs for the live, generated API explorer.

Routes are thin on purpose: validate input, call the data_source seam, shape the
result into a Pydantic model, raise 404 on misses. No business logic lives here —
that's either in the pipeline (triage/filters) or, later, behind the seam.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import data_source as ds
from . import fetch_runner
from .models import JobDetail, JobSummary, MarkdownDoc

DURATIONS = {"1d", "3d", "1w"}

app = FastAPI(
    title="Job-Hunt API",
    version="0.1.0",
    summary="Read-only API over the job-hunt pipeline artifacts (Phase B).",
)

# The React dev server (Phase C) runs on a different origin (Vite :5173 / CRA :3000),
# so the browser will block its fetches without CORS. Allow the usual local dev ports.
# Tighten to the real origin when this is deployed (Phase F).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness + a quick count so a smoke test confirms the data is actually wired."""
    return {"status": "ok", "jobs": len(ds.list_jobs())}


# --- Jobs ----------------------------------------------------------------------

@app.get("/jobs", response_model=list[JobSummary])
def get_jobs(
    status: str | None = Query(None, description="Filter by status: new|shortlisted|applied|skipped"),
    verdict: str | None = Query(None, description="Filter by triage_verdict: strong fit|fit|stretch|reject"),
    window: int | None = Query(None, ge=1, description="Dashboard VIEW: only jobs posted within N days OR touched by a human (durable-pool filter). Omit for the full pool."),
) -> list[JobSummary]:
    """List jobs as summaries (no description), strongest verdict first.

    Two modes: with `window`, returns the durable-pool dashboard VIEW (this run's fresh
    results plus anything approved/applied/noted, regardless of age — Phase D). Without it,
    returns the full pool, optionally filtered by status/verdict."""
    if window is not None:
        return [JobSummary.from_record(r) for r in ds.dashboard_jobs(window_days=window)]
    return [JobSummary.from_record(r) for r in ds.list_jobs(status=status, verdict=verdict)]


@app.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str) -> JobDetail:
    """Full record for one job, including the description and triage trail."""
    rec = ds.get_job(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    return JobDetail.from_record(rec)


class JobActionPatch(BaseModel):
    """Body for PATCH /jobs/{id} — the first WRITE endpoint. All fields optional; only the
    provided ones change. status drives Approve (shortlisted) / Remove (skipped, soft)."""
    status: str | None = None        # new | shortlisted | applied | skipped
    notes: str | None = None
    applied_date: str | None = None  # ISO date string


_STATUSES = {"new", "shortlisted", "applied", "skipped"}


@app.patch("/jobs/{job_id}", response_model=JobDetail)
def patch_job(job_id: str, patch: JobActionPatch) -> JobDetail:
    """Persist a human review action (status / notes / applied-date) — makes the previously
    LOCAL-ONLY dashboard actions survive a refresh. Writes job_actions, never the ad row."""
    if patch.status is not None and patch.status not in _STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(_STATUSES)}")
    rec = ds.patch_job_action(
        job_id, status=patch.status, notes=patch.notes, applied_date=patch.applied_date
    )
    if rec is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    return JobDetail.from_record(rec)


# --- Fetch: trigger an ingestion run + poll its status -------------------------
# The first WRITE path in the API: the dashboard "Go fetch" button drives this. The run
# happens in a background thread (fetch_runner) because it's slow; the UI polls /fetch/status.

class FetchRequest(BaseModel):
    sources: list[str] | None = None  # None → all available sources
    duration: str = "1d"              # 1d | 3d | 1w


@app.get("/sources", response_model=list[str])
def get_sources() -> list[str]:
    """Source ids the user can toggle in the Go-fetch dialog (don't hardcode in the UI)."""
    return fetch_runner.available_sources()


@app.post("/fetch")
def post_fetch(req: FetchRequest) -> dict:
    """Start a fetch (wipe + refill the pool) in the background. 409 if one is running."""
    valid = set(fetch_runner.available_sources())
    if req.sources is not None:
        unknown = [s for s in req.sources if s not in valid]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown sources: {unknown}")
        if not req.sources:
            raise HTTPException(status_code=400, detail="Select at least one source")
    if req.duration not in DURATIONS:
        raise HTTPException(status_code=400, detail=f"duration must be one of {sorted(DURATIONS)}")
    try:
        return fetch_runner.start(sources=req.sources, duration=req.duration)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/fetch/status")
def get_fetch_status() -> dict:
    """Current/last run state: idle|running|done|error, phase, counts, timestamps."""
    return fetch_runner.get_status()


@app.get("/fetch/wait")
def get_fetch_wait() -> dict:
    """Long-poll: block until the in-flight run finishes (or ~90s elapses), then return
    the final status. One held request instead of the client polling — the results view
    awaits this, then loads the fresh pool. Returns immediately if no run is in flight."""
    return fetch_runner.wait(timeout=90.0)


# --- Markdown docs: profile / dossiers / cover letters -------------------------

def _doc_or_404(slug: str, text: str | None, kind: str) -> MarkdownDoc:
    if text is None:
        raise HTTPException(status_code=404, detail=f"No {kind} {slug!r}")
    return MarkdownDoc(slug=slug, markdown=text)


@app.get("/profile", response_model=list[str])
def get_profiles() -> list[str]:
    """Slugs of the candidate profile files (cv, criteria, experience-map, …)."""
    return ds.list_profiles()


@app.get("/profile/{name}", response_model=MarkdownDoc)
def get_profile(name: str) -> MarkdownDoc:
    return _doc_or_404(name, ds.get_profile(name), "profile")


@app.get("/dossiers", response_model=list[str])
def get_dossiers() -> list[str]:
    return ds.list_dossiers()


@app.get("/dossiers/{slug}", response_model=MarkdownDoc)
def get_dossier(slug: str) -> MarkdownDoc:
    return _doc_or_404(slug, ds.get_dossier(slug), "dossier")


@app.get("/cover-letters", response_model=list[str])
def get_cover_letters() -> list[str]:
    return ds.list_cover_letters()


@app.get("/cover-letters/{slug}", response_model=MarkdownDoc)
def get_cover_letter(slug: str) -> MarkdownDoc:
    return _doc_or_404(slug, ds.get_cover_letter(slug), "cover letter")
