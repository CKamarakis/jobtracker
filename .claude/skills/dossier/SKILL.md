---
name: dossier
description: Use when building or reviewing a company research dossier (funding, headcount, market position, leadership, culture, fit hooks) for a job Chris is considering. Encodes the dossier format and the sourcing discipline. Every factual claim must carry a source URL or be marked unknown.
---

# Dossier skill

Produces a **sourced company dossier** the human reads before applying or interviewing.
The dossier is decision-support, not marketing. Its value is accuracy: a blank beats a
wrong number.

## The one rule that matters most
**Never invent. Cite or mark unknown.**
- Every factual claim carries a source URL in parentheses right after it.
- If a fact isn't found, write `unknown / not disclosed` — never estimate, never infer a
  number from vibes. A wrong funding figure or headcount is worse than a blank.
- Mark inference as inference: prefix derived judgments with `Inference:` so the reader
  never mistakes your reasoning for a sourced fact.
- Prefer primary/reputable sources (company site, official filings, established press)
  over aggregators and SEO content. If only a weak source exists, say so.
- Date-stamp anything that goes stale (funding, headcount, news): `(as of <month year>)`.

## Format

Start with a 2-3 line **TL;DR**: what the company does, stage, and the single biggest
fit signal or red flag. Then these sections (omit a section only if genuinely nothing
is findable — say `unknown / not disclosed`, don't drop it silently):

- **What they do** — product, customers, business model. (source)
- **Stage & funding** — total raised, last round + amount + date, notable investors. (source, dated)
- **Size** — headcount or best-sourced estimate. (source, dated) — *this directly informs
  the <2000-employee hard filter in triage; flag clearly if it's near or over the line.*
- **Market position & competitors** — where they sit, main rivals, any moat. (source)
- **Recent signals** — last ~12 months: growth, layoffs, launches, leadership changes. (source, dated)
- **Leadership** — founders / CPO / who Chris would report to, and their calibre signals.
  (source) — *feeds the "founder/boss calibre" triage factor.*
- **Culture & red flags** — Kununu/Glassdoor patterns, public controversies, churn signals.
  (source) — be even-handed; note when signal is thin.
- **Fit hooks (tied to Chris's CV)** — genuine, specific connections between his background
  and this company/role. Read [profile/cv.md](../../../profile/cv.md) to ground these. These
  feed the cover-letter's optional customization and his interview prep. Only real hooks —
  no stretches.
- **Open questions for the human / interview** — what's unknown and worth asking, what to
  verify before applying.

## On location (don't over-flag)
Online/remote-first companies **commonly** have a quirky legal or registered address that
isn't where the team actually is — a different German city, a holding-company seat, etc.
This is normal and low-signal. Do NOT make a within-Germany address mismatch a headline or
treat it as a red flag. Mention it in passing if relevant.
**What actually matters: is the HQ / main operations OUTSIDE Germany?** If so, say it
plainly and early — that's the location fact Chris cares about. If HQ is in Germany (even
at a weird address), a one-liner is enough.

## Output
- Markdown, the sections above, claims each followed by their `(source URL)`.
- Save to `data/dossiers/<company-slug>.md` and report the path back.
- No salesmanship and no preamble — just the dossier.

<!--
NOTES FOR CHRIS — delete once read.

WHY THE FORMAT LIVES HERE, NOT IN A SEPARATE TEMPLATE FILE
cover-voice is thin and points at profile/cover-template.md because the master LETTER is
reusable content you edit independently of the skill. A dossier has no equivalent master
artifact — the format IS the doctrine, and nothing else consumes it. Externalizing it
would be indirection with no payoff. The "edit one rule, touch one file" test still passes:
the format rules live in exactly one place — this file.

WHY THE SOURCING RULES ARE THE HEART OF THIS SKILL
Research is the highest hallucination-risk step in the whole pipeline (numbers, dates,
funding). The citation + unknown discipline is what makes a web-tool agent trustworthy.
That's the real lesson here: a tool-using agent is only as good as the rules that keep it
honest about what it actually found vs. what it guessed.

WHAT YOU MIGHT ADD LATER
- A worked example dossier in this folder (reference/) if outputs drift in format.
- A short "good source vs. bad source" list if the agent keeps citing SEO junk.
- Later, the accumulated data/dossiers/ could seed a RAG corpus (out of scope now).
-->
