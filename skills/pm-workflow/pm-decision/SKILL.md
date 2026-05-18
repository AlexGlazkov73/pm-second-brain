---
name: pm-decision
description: Record one product decision as an atomic note with context, options, and rationale. Delegates file write + MOC update to pm-knowledge.pm-add-decision.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "fts_search"]
model_preference: primary
inputs: { rationale: "free-form sentence(s) from the user" }
---

# pm-decision

## When to Use

When the user phrases a product decision in the current chat — typical openers are "we decided", "the call is", "let's go with" — or when the slash command `/pm-decision` is invoked. The skill captures one atomic decision per invocation and delegates the write to `pm-knowledge.pm-add-decision`.

## Quick Reference

| Input | Source | Notes |
|---|---|---|
| `rationale` | Free-form sentence(s) from the user | Required input |
| Project | Inferred from user's input or recent chat | Used for FTS prefilter |
| Past decisions (≤5) | `fts_search` on the same project | Context for novelty check |
| Output destination | `decisions/{{date}}-{{slug}}.md` | Written by `pm-add-decision` |

## Procedure

1. Use current conversation as primary context.
2. `fts_search` for past 5 decisions on the same project (extract project from user's input or recent chat).
3. Compose the atomic note per `prompt.md` using `templates/decision-note.md`.
4. Show preview card: frontmatter + body + "would be saved to `decisions/{{date}}-{{slug}}.md`".
5. On Approve: hand off to `pm-knowledge.pm-add-decision` (it owns the write and MOC update).
6. After write: if the pattern criterion is met (≥3 decisions same project + BM25 similarity ≥ `evolution.pattern_threshold` to a new candidate "rule"), append a one-line suggestion to `_brain/MEMORY.md` under `## Auto-synthesis suggestions`. Never auto-apply MEMORY edits beyond appending suggestions.
7. Emit audit event `decision-recorded`.

## Pitfalls

- This skill does not write the decision file itself — the write is owned by `pm-knowledge.pm-add-decision`. Calling Write directly here would create a duplicate.
- Never auto-apply MEMORY edits beyond appending suggestions under `## Auto-synthesis suggestions`.
- Do not skip the preview card; the user must Approve / Edit / Reject before any hand-off.
- If project cannot be inferred confidently, ask before invoking `fts_search`.

## Verification

- `pm-knowledge.pm-add-decision` was invoked exactly once after Approve.
- Audit event `decision-recorded` was emitted.
- If pattern criterion fired, a single new line appears under `_brain/MEMORY.md` `## Auto-synthesis suggestions`; no other section of MEMORY was edited.
