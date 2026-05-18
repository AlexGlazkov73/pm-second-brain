---
name: pm-workflow
description: Regular product-manager workflows over a personal Obsidian vault. Use for daily briefs, decision logging, and Q&A research.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write", "fts_search", "fts_index"]
model_preference: primary
---

# pm-workflow

## When to Use

When the user requests a regular daily, decision-logging, or vault-research action and there is not yet a more specific leaf skill loaded. The namespace skill is the dispatch table for everyday PM operations over the Obsidian vault.

## Quick Reference

| Trigger | Leaf | Cost target |
|---|---|---|
| Cron at 08:00 weekdays, or user says "what's on today" | `pm-daily-brief` | ~$0.02 |
| User starts a sentence with "we decided" / "the call is" / runs `/pm-decision` | `pm-decision` | ~$0.04 |
| User asks a question about past vault content | `pm-research` | ~$0.04 |
| Meeting transcript dropped into chat (v1) | `pm-meeting-recap` (skeleton) | n/a |

## Procedure

1. Inspect the user request and the most recent assistant turn for one of the triggers in the Quick Reference table.
2. Load the matching leaf SKILL.md only on first invocation in the session.
3. Hand off to the leaf skill; do not duplicate its Procedure here.

## Pitfalls

- Do not load more than one leaf at a time — stay under 25% context budget.
- Do not invoke `pm-meeting-recap` in v0: it is a skeleton placeholder for v1.
- Do not write to the vault from this namespace skill directly; writes only happen inside a leaf.

## Verification

- Exactly one leaf SKILL.md is loaded after dispatch.
- The selected leaf's `When to Use` block matches the actual user trigger.
