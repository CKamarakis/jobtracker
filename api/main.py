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

from . import data_source as ds
from .models import JobDetail, JobSummary, MarkdownDoc

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
) -> list[JobSummary]:
    """List jobs as summaries (no description), optionally filtered, strongest verdict first."""
    return [JobSummary.from_record(r) for r in ds.list_jobs(status=status, verdict=verdict)]


@app.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str) -> JobDetail:
    """Full record for one job, including the description and triage trail."""
    rec = ds.get_job(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    return JobDetail.from_record(rec)


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
