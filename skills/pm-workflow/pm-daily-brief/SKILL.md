---
name: pm-daily-brief
description: Compose a daily brief in daily/<today>.md from MOCs, calendar events, open tickets, and yesterday's action items. Token budget ~4k in / ~2k out.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write", "fts_search"]
model_preference: primary
inputs: { date: "YYYY-MM-DD (defaults to today, vault tz)" }
---

# pm-daily-brief

## When to Use

When the morning cron (`0 8 * * 1-5`) fires, or when the user explicitly asks "what's on today" / "morning brief" / "today's plan", and no `daily/<today>.md` exists yet.

## Quick Reference

| Step | Output | Token cost |
|---|---|---|
| Read MOCs (`Index.md`, `Projects.md`, `Decisions.md`) | ~1.5k tok in | low |
| CalDAV events for today | one section | optional |
| Tracker open tickets | one section | optional |
| Carry-over action items | one section | low |

## Procedure

1. Read `mocs/Index.md` (small, ~500 tok).
2. Read `mocs/Projects.md` + `mocs/Decisions.md` (~1k tok).
3. Call `caldav.list_events(today)` if enabled; else skip events section.
4. Call `yandex-tracker.my_tickets(open)` if enabled.
5. Read `daily/<yesterday>.md` for carry-over action items.
6. Render per `prompt.md` using `templates/daily-note.md`.
7. Show preview card with Approve / Edit / Reject.
8. On Approve: write `daily/<today>.md`; if any new action items appear under a project, append a one-liner to `mocs/Projects.md`.
9. Emit audit event `daily-brief-written` with token counts.

## Pitfalls

- Never overwrite an existing `daily/<today>.md` without explicit confirmation.
- If CalDAV / Tracker MCP is unreachable, write the brief without the section and log a warning in the audit.
- Do not invent calendar events — if the CalDAV call fails, omit the section entirely.

## Verification

- File `daily/<today>.md` now exists.
- An `audit.jsonl` entry of type `daily-brief-written` was appended with non-zero token counts.
- No frontmatter or body section of `mocs/Projects.md` was deleted (the carry-over append is additive).
