---
name: cover-voice
description: Use when drafting, revising, or reviewing a cover letter for Chris Kamarakis. Encodes the fixed voice, structure, and customization rules. Defaults to leaving the master template untouched — restraint beats over-customization.
---

# Cover-voice skill

When invoked: read [profile/cover-template.md](../../../profile/cover-template.md) and apply it. That file is the single source of voice rules, customization rules, the master prose, and output format. Do not improvise — the doctrine lives there.

## Safety net (do not forget, even if you skim the template)
- **Never invent facts** about Chris or the company. If a hook isn't genuinely true, leave the master text.
- **Output the letter only.** No preamble like "Here is your cover letter." No commentary. Just the letter.

<!--
NOTES FOR CHRIS — delete this comment block once you've read it.

WHY THIS FILE IS NOW THIN
The previous version of this SKILL.md duplicated the voice rules, customization rules, and output rules from cover-template.md. If you changed "max 250 words" you'd have had to edit two files. Separation of files ≠ separation of concerns. The test for a good split is: edit one rule, touch one file. The old version failed that test.

DIVISION OF LABOR
- This file owns: WHEN to apply (frontmatter description), and a tiny safety net of 1catastrophic-to-forget rules.
- cover-template.md owns: WHAT to apply — voice rules, customization rules, the master prose, output format. The full doctrine.

WHY THE SAFETY-NET BULLETS REPEAT
Two rules are repeated here on purpose:
- "Never invent facts" — the failure mode that destroys trust. Worth restating.
- "Output the letter only" — the most common LLM failure mode (adding "Here is your cover letter:" preamble).
These are stable, won't drift, and worth seeing even if the agent never opens cover-template.md.

Everything else (word count, paragraph rules, etc.) lives in ONE place: the template.

HOW IT GETS LOADED
Claude Code's skill loader matches a user's request against the `description` field above. When a match fires, this SKILL.md is loaded into the agent's context. The agent then reads cover-template.md as instructed by the body above.

WHAT YOU MIGHT WANT TO ADD LATER
- Bundled reference letters in this folder (e.g., `reference/good-examples/`). Skills can ship with extra files alongside SKILL.md. Add only if drafts keep drifting in the same wrong direction and you want to anchor with examples.
- A bad-output gallery in cover-template.md if specific phrasings keep sneaking in (corporate-speak, hard-sells). It belongs in the template, not here — it's doctrine.

WHAT NOT TO ADD HERE
- Voice rules, customization rules, output rules beyond the two-bullet safety net. Those drift; they belong in one place.
- Examples of letters. Those are content, not dispatch.
- Anything that, when you change it, would require you to also change cover-template.md.

-->
