"""db/engine.py — SQLAlchemy engine + session factory.

One engine per process (it owns the connection pool); a Session is short-lived and
per-unit-of-work. The connection string comes from $DATABASE_URL so the same code
points at portable-dev PG today and a containerized/hosted PG later (G6/F) with zero
code change — that connection-string-agnosticism is exactly why Docker could be
deferred out of Phase D.

`session_scope()` is the context-managed unit of work: commit on success, rollback on
error, always close. Repository functions use it so callers never juggle sessions by
hand. (FastAPI routes could instead use a per-request dependency later; for now the
repository owns its own short transactions, which keeps ingest — a non-web caller —
working the same way.)
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# psycopg (v3) driver. Default points at the portable local dev DB stood up in
# docs/ENV.md. Never hardcode credentials for a real deployment — override via env.
DEFAULT_URL = "postgresql+psycopg://jobhunt:jobhunt@localhost:5433/jobhunt"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_URL)

# future=True is the 2.0 style (default in SA 2.x, kept explicit for clarity).
# pool_pre_ping avoids handing out a dead connection after the DB restarts — cheap
# insurance for a laptop DB that gets stopped/started a lot.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on clean exit, rollback on exception, always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
