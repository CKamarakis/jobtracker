"""api/fetch_runner.py — runs a fetch in the background and tracks its status.

The "Go fetch" button can't be a synchronous request: an ingest run makes live API/web
calls over many seconds. So POST /fetch starts a run in a daemon thread and returns
immediately; the frontend polls GET /fetch/status until it reaches done/error.

Why a thread (not FastAPI BackgroundTasks): ingest is blocking, synchronous urllib I/O.
A thread keeps the event loop free and lets a single-user local app poll progress without
a queue/worker. Status lives in a module-global guarded by a lock AND is mirrored to
data/run_status.json so a fresh server (or a page reload) can still read the last run.

LLM-free for now (Step 1): this drives ingestion only. The triage stage is layered on
the same run in Step 2 — it will report through the same `progress` callback / phases.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = REPO_ROOT / "data" / "run_status.json"

# ingest/ isn't an installed package; reuse the same path trick data_source.py uses so we
# can import the orchestrator (one source of truth for the run).
sys.path.insert(0, str(REPO_ROOT / "ingest"))
import run as ingest_run  # noqa: E402  (path-dependent import, intentional)

_lock = threading.Lock()
_state: dict = {
    "state": "idle",        # idle | running | done | error
    "phase": None,          # fetch | write | triage | done | error
    "message": None,
    "counts": None,         # latest progress counts / final summary
    "sources": None,
    "duration": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status() -> None:
    try:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATUS_PATH.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # status persistence is best-effort; never fail a run over it


def _load_status() -> None:
    """Hydrate from disk at import. A 'running' state on disk is stale (no live thread
    survived the restart) → coerce to idle so the UI doesn't wait on a ghost run."""
    try:
        saved = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if saved.get("state") == "running":
        saved["state"] = "idle"
        saved["phase"] = None
        saved["message"] = "previous run interrupted"
    _state.update(saved)


def _set(**kw) -> None:
    with _lock:
        _state.update(kw)
        _write_status()


def _progress(phase: str, message: str, counts: dict | None = None) -> None:
    _set(phase=phase, message=message, counts=counts)


def _run(sources: list[str] | None, duration: str) -> None:
    try:
        summary = ingest_run.run_ingest(sources=sources, duration=duration, progress=_progress)
        # Triage stage (LLM). Non-fatal: if it fails, ingestion already succeeded — the pool
        # is populated, jobs are just unscored, so report the error without failing the run.
        try:
            from . import triage_runner
            summary["triage"] = triage_runner.triage_pool(progress=_progress)
        except Exception as e:  # noqa: BLE001
            summary["triage"] = {"error": str(e)}
        _set(state="done", phase="done", message="fetch complete",
             counts=summary, finished_at=_now(), error=None)
    except Exception as e:  # noqa: BLE001 — surface any run failure as error status
        _set(state="error", phase="error", message=str(e), error=str(e), finished_at=_now())


def available_sources() -> list[str]:
    return ingest_run.available_sources()


def get_status() -> dict:
    with _lock:
        return dict(_state)


def start(sources: list[str] | None, duration: str) -> dict:
    """Kick a fetch in a daemon thread. Raises RuntimeError if one is already running."""
    with _lock:
        if _state["state"] == "running":
            raise RuntimeError("a fetch is already running")
        _state.update(
            state="running", phase="starting", message="starting fetch", counts=None,
            sources=sources, duration=duration, started_at=_now(), finished_at=None, error=None,
        )
        _write_status()
        snapshot = dict(_state)
    threading.Thread(target=_run, args=(sources, duration), daemon=True).start()
    return snapshot


_load_status()
