"""db/ — the persistence engine for Phase D (Postgres behind the seam).

This package is the ONLY place that knows about SQLAlchemy/Postgres. Both callers
import it:
  - api/data_source.py delegates its bodies here (React/routes never notice).
  - ingest/run.py upserts the fetched pool through it.

It deliberately imports NO web stack (no FastAPI/Pydantic) so ingest can use it
standalone (`./py.ps1 ingest/run.py`) and so it stays unit-testable without uvicorn.
That no-web rule is also why this is its own package and not part of api/ — putting
it in api/ would make `ingest -> api -> fastapi` a hard import chain.
"""
