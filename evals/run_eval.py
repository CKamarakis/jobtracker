"""evals/run_eval.py — blind triage eval runner.

Reads evals/labeled/*.md, sends each ad body to the triage subagent (blind to the
human verdict), and compares the agent's verdict to the labeled one. Reports
exact / adjacent / far disagreements and writes a raw run log to evals/runs/.

Usage:
    pip install -r evals/requirements.txt
    python evals/run_eval.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELED_DIR = REPO_ROOT / "evals" / "labeled"
RUNS_DIR = REPO_ROOT / "evals" / "runs"
CRITERIA_PATH = REPO_ROOT / "profile" / "criteria.md"
PARAMETERS_PATH = REPO_ROOT / "profile" / "parameters.md"
CV_PATH = REPO_ROOT / "profile" / "cv.md"
TRIAGE_PATH = REPO_ROOT / ".claude" / "agents" / "triage.md"

# Ordered weakest-to-strongest is irrelevant; what matters is the ordinal positions
# so we can call out adjacent (off-by-one) vs far (off-by-two-or-more) disagreements.
VERDICT_ORDER = ["strong fit", "fit", "stretch", "reject"]

# Triage subagent's model. Matches the `model:` field in .claude/agents/triage.md.
MODEL = "claude-sonnet-4-6"


def parse_labeled_file(path: Path) -> dict:
    """Read a labeled .md and split YAML frontmatter from the ad body."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter in {path}")
    fm_text, body = match.groups()
    fm = {}
    for line in fm_text.strip().split("\n"):
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return {"frontmatter": fm, "body": body.strip(), "path": path}


def parse_triage_md(path: Path) -> str:
    """Extract the system prompt body from triage.md (everything after the frontmatter)."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n.*?\n---\n(.*)$", text, re.DOTALL)
    body = match.group(1).strip() if match else text
    # Strip the HTML-comment notes block (instructions for Chris, not for the agent).
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
    return body


def build_system_prompt() -> str:
    """Compose the full static prefix: triage prompt + criteria.md + parameters.md + cv.md.

    Inlining the reference files means the agent doesn't need Read tool — the API call
    is self-contained and reproducible. Same bytes every call → cache hit.

    parameters.md is inlined because criteria.md now references it for the value lists and
    the weighted soft-factor form — the agent must see the same rubric the eval tests.
    """
    triage = parse_triage_md(TRIAGE_PATH)
    criteria = CRITERIA_PATH.read_text(encoding="utf-8")
    parameters = PARAMETERS_PATH.read_text(encoding="utf-8")
    cv = CV_PATH.read_text(encoding="utf-8")
    return (
        f"{triage}\n\n"
        f"---\n\n# REFERENCE: profile/criteria.md\n\n{criteria}\n\n"
        f"---\n\n# REFERENCE: profile/parameters.md\n\n{parameters}\n\n"
        f"---\n\n# REFERENCE: profile/cv.md\n\n{cv}\n"
    )


def extract_verdict(agent_text: str) -> str | None:
    """Find the verdict in the agent's output. Returns None if unparseable."""
    # Normal output: **Verdict:** `<value>` — reason
    match = re.search(
        r"\*\*Verdict:\*\*\s*`?(strong fit|fit|stretch|reject)`?",
        agent_text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).lower()
    # Hard-filter reject collapsed form: `reject` (reason)
    if re.search(r"`reject`", agent_text, re.IGNORECASE):
        return "reject"
    return None


def classify_agreement(agent: str | None, user: str) -> str:
    if agent is None:
        return "unparsed"
    if agent == user:
        return "exact"
    ai = VERDICT_ORDER.index(agent)
    ui = VERDICT_ORDER.index(user)
    return "adjacent" if abs(ai - ui) == 1 else "far"


def run_eval():
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set. Put it in .env and re-run.")

    client = anthropic.Anthropic()
    system_prompt = build_system_prompt()

    labeled_files = sorted(LABELED_DIR.glob("*.md"))
    if not labeled_files:
        sys.exit(f"No labeled files in {LABELED_DIR}")

    results = []
    print(f"Running triage on {len(labeled_files)} labeled jobs (model: {MODEL})\n")

    for i, path in enumerate(labeled_files, 1):
        case = parse_labeled_file(path)
        fm = case["frontmatter"]
        user_verdict = fm.get("verdict", "").lower().strip()
        title = fm.get("title", "")
        company = fm.get("company", "")

        if user_verdict not in VERDICT_ORDER:
            print(f"  [{i}/{len(labeled_files)}] SKIP {path.name} — verdict placeholder")
            continue

        print(f"  [{i}/{len(labeled_files)}] {company} — {title} ... ", end="", flush=True)

        # The system prompt is identical for every call — perfect cache prefix.
        # cache_control on the system block tells the API to write/read the cache.
        # First call writes (you'll see cache_creation_input_tokens), subsequent
        # calls read (cache_read_input_tokens). ~90% discount on the cached bytes.
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            # temperature=0 for eval determinism: at temp 1.0 the run-to-run jitter
            # (±1-2 cases on n=18) is the same size as the rubric deltas we're measuring,
            # so a single run can't separate a real improvement from noise. Pin it.
            temperature=0,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Triage this job ad:\n\n---\n\n{case['body']}",
                }
            ],
        )

        agent_text = next(b.text for b in response.content if b.type == "text")
        agent_verdict = extract_verdict(agent_text)
        agreement = classify_agreement(agent_verdict, user_verdict)

        print(f"{agreement} (you: {user_verdict} / agent: {agent_verdict})")

        results.append(
            {
                "file": path.name,
                "company": company,
                "title": title,
                "user_verdict": user_verdict,
                "user_reason": fm.get("reason", ""),
                "user_confidence": fm.get("confidence", ""),
                "agent_verdict": agent_verdict,
                "agent_output": agent_text,
                "agreement": agreement,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "cache_creation": response.usage.cache_creation_input_tokens,
                    "cache_read": response.usage.cache_read_input_tokens,
                },
            }
        )

    # ----- Summary -----
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    counts = {k: sum(1 for r in results if r["agreement"] == k)
              for k in ("exact", "adjacent", "far", "unparsed")}
    n = len(results)
    print(f"  Exact:    {counts['exact']}/{n}")
    print(f"  Adjacent: {counts['adjacent']}/{n}  (off by one — tuning)")
    print(f"  Far:      {counts['far']}/{n}  (off by 2+ — investigate)")
    if counts["unparsed"]:
        print(f"  Unparsed: {counts['unparsed']}/{n}  (agent output didn't match expected format)")

    disagreements = [r for r in results if r["agreement"] != "exact"]
    if disagreements:
        print("\nDISAGREEMENTS (the signal):")
        for r in disagreements:
            print(f"\n  {r['company']} — {r['title']}")
            print(f"    You:   {r['user_verdict']} ({r['user_confidence']}) — {r['user_reason'][:120]}")
            print(f"    Agent: {r['agent_verdict']} ({r['agreement']})")

    # Cache stats — sanity check that caching is actually firing
    cache_reads = sum(r["usage"]["cache_read"] for r in results)
    cache_writes = sum(r["usage"]["cache_creation"] for r in results)
    print(f"\nCache: {cache_writes} tokens written, {cache_reads} read across {n} calls")
    if cache_reads == 0 and n > 1:
        print("  ⚠️  No cache hits across multiple calls — prefix may be changing between requests")

    # ----- Persist raw run log -----
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = RUNS_DIR / f"{timestamp}.json"
    log_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull run log: {log_path.relative_to(REPO_ROOT)}")
    print("(Inspect agent_output for full reasoning on disagreements.)")


if __name__ == "__main__":
    run_eval()
