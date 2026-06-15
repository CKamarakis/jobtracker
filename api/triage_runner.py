"""api/triage_runner.py — score newly-fetched jobs with an LLM, after ingestion.

This is the LLM half of the "Go fetch" seam. Ingestion (deterministic) lands `new` jobs;
this stage assigns each a triage verdict so the dashboard/list show scored results.

SEAM (see memory: project_triage_llm_seam):
- Provider = `claude-agent-sdk` running against Chris's existing Claude subscription, so a
  run costs ~$0 marginal. Built behind a tiny provider boundary (`_score_batch`) so it can
  later swap to a local Ollama model or the metered Anthropic API without touching callers.
- DRIFT CONTROL: the system prompt is the real `.claude/agents/triage.md` body plus the same
  `profile/*.md` files the subagent reads — inlined here at runtime (read fresh from disk),
  so the on-disk files stay the single source of truth. Inlining (vs. letting the agent Read)
  keeps the call a deterministic single turn with no tool-permission surface.

SEEN-GUARD: `data/triage_cache.json` maps job id → cached verdict. The pool is wiped every
fetch, so without this every run would re-score ads seen yesterday. Repeats hydrate from the
cache for free; only genuinely-new jobs hit the LLM.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = REPO_ROOT / "data" / "jobs.jsonl"
CACHE_PATH = REPO_ROOT / "data" / "triage_cache.json"
AGENT_PATH = REPO_ROOT / ".claude" / "agents" / "triage.md"
PROFILE_DIR = REPO_ROOT / "profile"
# The profile files the triage subagent reads, in the order its instructions name them.
PROFILE_FILES = ("criteria.md", "parameters.md", "cv.md", "experience-map.md")

VALID_VERDICTS = {"strong fit", "fit", "stretch", "reject"}
BATCH_SIZE = 12          # jobs per LLM call — small enough to stay reliable
MAX_DESC_CHARS = 4000    # cap a single description so one huge ad can't blow the prompt

# Short role line — this is the ONLY thing passed as a CLI flag to the bundled claude.exe.
# Windows caps a command line at ~32k chars, so the big instruction+profile block must NOT
# go here; it rides the user message (streamed over stdin). See the WinError 206 fix.
SYSTEM_ROLE = (
    "You are a precise job-triage scorer. Everything you need is in the user message. "
    "Do NOT use any tools and do NOT read files — all reference material is inlined. "
    "Respond in a single message containing only the JSON array specified — no prose, no fence."
)

sys.path.insert(0, str(REPO_ROOT / "ingest"))
import store  # noqa: E402  (path-dependent import, intentional — same loader as ingest/API)


# ── Prompt assembly ───────────────────────────────────────────────────────────

def _strip_agent_frontmatter(md: str) -> str:
    """Drop the YAML frontmatter and the trailing NOTES-FOR-CHRIS HTML comment from
    triage.md, leaving just the system-prompt body."""
    body = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.DOTALL)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    return body.strip()


def _build_instructions() -> str:
    """triage.md instructions + the profile files it reads, inlined. Read fresh each run so
    the on-disk files remain the single source of truth. Goes in the USER message (stdin),
    not system_prompt — see SYSTEM_ROLE for why."""
    instructions = _strip_agent_frontmatter(AGENT_PATH.read_text(encoding="utf-8"))
    parts = [
        # Override banner FIRST — the triage.md body says "Read these first", but the files
        # are inlined below. Without this the model tries the Read tool → needs a 2nd turn →
        # "Reached maximum number of turns" error. Neutralize it up front.
        "IMPORTANT: Do NOT use any tools and do NOT read any files. Every reference file the "
        "instructions mention is inlined verbatim below. Score using only this message and "
        "reply in ONE turn.\n\n",
        instructions,
        "\n\n# Reference files (inlined — already provided, do not look for them on disk)\n",
    ]
    for name in PROFILE_FILES:
        path = PROFILE_DIR / name
        if path.exists():
            parts.append(f"\n## profile/{name}\n\n{path.read_text(encoding='utf-8')}\n")
    parts.append(
        "\n\n# OUTPUT CONTRACT (override the prose format above)\n"
        "Return ONLY a JSON array — no markdown, no commentary, no code fence. One object "
        "per job in the input, each exactly:\n"
        '{"id": "<the job id>", "verdict": "strong fit|fit|stretch|reject", '
        '"fit": "<one sentence>", "anti_fit": "<one sentence>", "reason": "<one line>"}\n'
        "Use the job id given in the input verbatim. Include every job. Output nothing but the array."
    )
    return "".join(parts)


def _job_payload(rec: dict) -> dict:
    desc = rec.get("description") or ""
    if len(desc) > MAX_DESC_CHARS:
        desc = desc[:MAX_DESC_CHARS] + " …[truncated]"
    return {
        "id": rec["id"],
        "company": rec.get("company"),
        "title": rec.get("title"),
        "location": rec.get("location"),
        "alt_locations": rec.get("alt_locations"),
        "remote": rec.get("remote"),
        "posted_date": rec.get("posted_date"),
        "url": rec.get("url"),
        "description": desc,
    }


def _parse_verdicts(text: str) -> list[dict]:
    """Tolerantly pull the JSON array out of the model's reply (handles stray prose/fences)."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON array in model output: {text[:200]!r}")
    return json.loads(text[start : end + 1])


# ── Provider boundary (swap target: ollama / anthropic API later) ──────────────

async def _score_batch_claude_sdk(instructions: str, jobs: list[dict]) -> str:
    """Run one batch through claude-agent-sdk against the local Claude subscription.
    Returns the raw assistant text. Imported lazily so the API boots without the SDK.

    The big `instructions` block (triage logic + profile) goes in the user message, NOT in
    system_prompt — the SDK passes system_prompt as a CLI flag and Windows caps the command
    line at ~32k chars (WinError 206). Only the short SYSTEM_ROLE rides the flag."""
    from claude_agent_sdk import query, AssistantMessage, TextBlock, ClaudeAgentOptions

    # allowed_tools=[] → the model can't call tools, so it answers in a single turn.
    # max_turns=2 is a safety net in case it still emits a stray non-text block first.
    opts = ClaudeAgentOptions(
        system_prompt=SYSTEM_ROLE, allowed_tools=[], max_turns=2, cwd=str(REPO_ROOT)
    )
    user = (
        instructions
        + "\n\n# Jobs to score (return the JSON array per the output contract)\n\n"
        + json.dumps(jobs, ensure_ascii=False, indent=2)
    )
    chunks: list[str] = []
    async for msg in query(prompt=user, options=opts):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
    return "".join(chunks)


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # cache is an optimization; never fail a run over it


def _apply(rec: dict, v: dict, now: str) -> None:
    rec["triage_verdict"] = v["verdict"]
    rec["triage_fit"] = v.get("fit")
    rec["triage_anti_fit"] = v.get("anti_fit")
    rec["triage_reason"] = v.get("reason")
    rec["triaged_date"] = v.get("triaged_date", now)


# ── Orchestration ─────────────────────────────────────────────────────────────

async def _run(progress=None) -> dict:
    import anyio  # noqa: F401  (ensure event-loop lib present; query() is anyio-based)

    def emit(msg: str, counts: dict | None = None) -> None:
        if progress:
            progress("triage", msg, counts)

    jobs = store.load_jobs(JOBS_PATH)
    cache = _load_cache()
    now = datetime.now(timezone.utc).isoformat()

    # Candidates: admitted, untriaged jobs. (skipped/expired already carry skip_reason.)
    candidates = [r for r in jobs.values()
                  if r.get("status") == "new" and not r.get("triage_verdict")]

    cached = to_score = 0
    pending: list[dict] = []
    for rec in candidates:
        hit = cache.get(rec["id"])
        if hit and hit.get("verdict") in VALID_VERDICTS:
            _apply(rec, hit, now)
            cached += 1
        else:
            pending.append(rec)
    to_score = len(pending)

    emit(f"triaging {to_score} new jobs ({cached} from cache)",
         {"to_score": to_score, "cached": cached})

    scored = failed = 0
    errors: list[str] = []
    instructions = _build_instructions() if pending else ""
    by_id = {r["id"]: r for r in pending}

    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        emit(f"scoring jobs {i + 1}-{i + len(batch)} of {to_score}",
             {"to_score": to_score, "scored": scored, "cached": cached})
        try:
            raw = await _score_batch_claude_sdk(instructions, [_job_payload(r) for r in batch])
            verdicts = _parse_verdicts(raw)
        except Exception as e:  # noqa: BLE001 — one bad batch shouldn't sink the rest
            failed += len(batch)
            if len(errors) < 5:
                errors.append(str(e)[:300])
            emit(f"batch failed: {e}")
            continue
        for v in verdicts:
            rec = by_id.get(v.get("id"))
            if rec is None or v.get("verdict") not in VALID_VERDICTS:
                continue
            _apply(rec, v, now)
            cache[rec["id"]] = {
                "verdict": v["verdict"], "fit": v.get("fit"),
                "anti_fit": v.get("anti_fit"), "reason": v.get("reason"), "triaged_date": now,
            }
            scored += 1

    store.save_jobs(JOBS_PATH, jobs)
    _save_cache(cache)

    summary = {"candidates": len(candidates), "cached": cached, "scored": scored, "failed": failed}
    if errors:
        summary["errors"] = errors
    emit("triage complete", summary)
    return summary


def triage_pool(progress=None) -> dict:
    """Score all untriaged `new` jobs in the pool (sync entry point for the fetch runner)."""
    import anyio
    return anyio.run(_run, progress)
