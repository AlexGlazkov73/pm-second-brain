---
name: pm-knowledge
description: Maintain the vault knowledge graph — create atomic notes with valid frontmatter and link them through MOC files.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write", "fts_search", "fts_index"]
model_preference: primary
---

# pm-knowledge

## When to Use

When new knowledge needs to be captured into the vault (decisions, meetings, links between notes), the namespace skill dispatches to the appropriate write-only leaf. Used both interactively and by background jobs.

## Quick Reference

| Trigger | Leaf |
|---|---|
| `pm-workflow.pm-decision` approved a new decision | `pm-add-decision` (writes file + updates MOC) |
| New meeting note needed | `pm-add-meeting` |
| Cron / on-demand: link recent notes to similar notes | `pm-link-notes` |
| User says "rebuild MOC for X" | `pm-rebuild-moc` |

## Procedure

1. Match the user input or upstream skill's hand-off to a leaf via the Quick Reference table.
2. Load only the matched leaf SKILL.md.
3. Delegate execution. Never duplicate work: if `pm-workflow.pm-decision` already wrote the file, call `pm-add-decision` only for MOC update.

## Pitfalls

- Never overwrite an existing knowledge file — knowledge capture is append-only.
- Do not invent wikilinks; only emit `[[…]]` for targets that exist in the vault.

## Verification

- A new file was created or appended under `decisions/`, `meetings/`, or the active note's links section.
- The audit log received exactly one `pm-knowledge-*` event.
