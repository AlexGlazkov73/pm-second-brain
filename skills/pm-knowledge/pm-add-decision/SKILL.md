---
name: pm-add-decision
description: Write a decision note file from a structured payload AND update mocs/Decisions.md and (optionally) mocs/Projects.md. Idempotent on the file path.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write", "fts_index"]
model_preference: primary
inputs: { payload: "{ date, slug, title, project, tags[], owner, context, options[], decision, rationale, consequences, links[] }", mode: "full | moc_only — default: full" }
---

# pm-add-decision

## When to Use

When an upstream skill (typically `pm-workflow.pm-decision`) has captured a structured decision payload and now needs the file written to disk and the surrounding MOCs updated. Also invoked in `moc_only` mode to refresh MOC entries for an already-written decision file.

## Quick Reference

| Field | Value |
|---|---|
| Target path | `decisions/{{date}}-{{slug}}.md` |
| Modes | `full` (default) — write file + update MOCs; `moc_only` — update MOCs only |
| Required template | `<vault_root>/templates/decision-note.md` |
| MOC files touched | `mocs/Decisions.md` (always if writable), `mocs/Projects.md` (soft optional) |
| Audit events | `decision-file-written` (full) / `decision-moc-updated` (moc_only) |
| Idempotency | Refuses to overwrite an existing target in `full` mode |

## Procedure

1. Compute target path: `decisions/{{date}}-{{slug}}.md`.
2. Read the target path.
   - If `mode == full` and file exists: refuse and surface a "file already exists, use /pm-overwrite" hint. Never silently overwrite. Stop here.
   - If `mode == moc_only` and file exists: proceed to Step 5 (skip Steps 3 and 4).
   - If `mode == moc_only` and file is missing: add `target file missing for moc_only mode` to `errors` and stop — do not proceed to Steps 3–7.
   - If `mode == full` and file does not exist: proceed to Step 3.
3. Read the template at `<vault_root>/templates/decision-note.md` (paths in this skill are resolved from the vault root). Render it with the payload, filling in all fields:
   - Frontmatter: `type`, `date`, `status` (fixed: `accepted`), `project`, `tags`, `owner`.
   - Body sections in order: `## Context`, `## Options considered`, `## Decision`, `## Rationale`, `## Consequences`, `## Links`.
   - Omit a section entirely (heading and body) if the payload field is empty or absent.
4. Write the rendered note to `decisions/{{date}}-{{slug}}.md`.
5. Read `mocs/Decisions.md`.
   - If `mocs/Decisions.md` does not exist: create it with just the new `## {{project}}` section containing the new bullet. No frontmatter required. Proceed to Step 6.
   - If `mocs/Decisions.md` exists but is unreadable: add `mocs/Decisions.md read error` to `errors` and skip the rest of Step 5 and Step 6.
   - If readable: locate the `## {{project}}` header (level-2, exact project name match, case-insensitive):
     - If found: insert `- [[decisions/{{date}}-{{slug}}]] — {{title}}` as a new bullet at the top of that section's list.
     - If not found: create a new `## {{project}}` section, insert the bullet, then re-sort all level-2 project headers alphabetically (case-insensitive). Preserve any `## Manual notes` section at its original position (do not sort it).
   Write the updated content back to `mocs/Decisions.md`.
6. Read `mocs/Projects.md`.
   - If `mocs/Projects.md` does not exist or is unreadable: do nothing — this is a soft optional update.
   - If readable: if a `## {{project}}` section exists and contains a `### Recent decisions` subheading:
     - Prepend `- [[decisions/{{date}}-{{slug}}]] — {{title}}` to the list under `### Recent decisions`.
     - Trim the list to at most 5 entries (drop the oldest).
     - Write the updated content back to `mocs/Projects.md`.
   - If `## {{project}}` is absent, or `### Recent decisions` is absent under it: do nothing to `mocs/Projects.md`.
7. Call `fts_index(path, title, body)` where `path` is `decisions/{{date}}-{{slug}}.md` and `title` is `{{title}}`. For `body`:
   - In `full` mode: use the rendered template content produced in Step 3.
   - In `moc_only` mode: read the existing file at `decisions/{{date}}-{{slug}}.md` to obtain its full content, and use that as `body`.
   If the call fails or times out, add `fts_index <error>` to `errors` and continue — do not roll back any writes.
8. Emit the audit event:
   - In `full` mode: emit `decision-file-written` with `{ files_written: [<decision-path>, <moc-files-actually-updated>] }` — include `mocs/Decisions.md` and `mocs/Projects.md` only if each was actually modified.
   - In `moc_only` mode: emit `decision-moc-updated` with `{ files_written: [<moc-files-actually-updated>] }` — list only the MOC files that were actually written (e.g. `mocs/Decisions.md`, optionally `mocs/Projects.md`). Do not include the decision file path.

## Pitfalls

- Never silently overwrite an existing decision file in `full` mode — refuse with a `/pm-overwrite` hint.
- In `moc_only` mode, if the target file is missing, stop immediately (do not run Steps 3-7).
- Do not roll back successful writes when `fts_index` fails; record the error and continue.
- Preserve any `## Manual notes` section at its original position when re-sorting `mocs/Decisions.md`.
- The `mocs/Projects.md` update is a *soft optional* — missing or unreadable file must not block success.

## Verification

- File `decisions/{{date}}-{{slug}}.md` exists at the computed path (in `full` mode).
- `mocs/Decisions.md` contains a bullet `- [[decisions/{{date}}-{{slug}}]] — {{title}}` under `## {{project}}`.
- If `mocs/Projects.md` had `### Recent decisions` under `## {{project}}`, the list now has the new bullet at the top and ≤5 entries total.
- Audit event `decision-file-written` (or `decision-moc-updated`) was emitted with the actual `files_written` list.
- The full content of the target file was passed to `fts_index` (in both modes), or an `fts_index <error>` was recorded.
