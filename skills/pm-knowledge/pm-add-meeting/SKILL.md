---
name: pm-add-meeting
description: Write a meeting note file from a structured payload AND update mocs/Decisions.md and (optionally) mocs/Projects.md. Idempotent on the file path.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write", "fts_index"]
model_preference: primary
inputs: { payload: "{ date, slug, title, project, participants[], tags[], decisions[], action_items[], open_questions[] }", mode: "full | moc_only — default: full" }
---

# pm-add-meeting

## When to Use

When an upstream skill (typically `pm-workflow.pm-meeting-recap` in v1) hands off a structured meeting payload and needs the meeting note written to disk plus the surrounding MOCs updated. Also invoked in `moc_only` mode to refresh MOC entries for an already-written meeting file.

## Quick Reference

| Field | Value |
|---|---|
| Target path | `meetings/{{date}}-{{slug}}.md` |
| Modes | `full` (default) — write file + update MOCs; `moc_only` — update MOCs only |
| Required template | `<vault_root>/templates/meeting-note.md` |
| MOC files touched | `mocs/Decisions.md` (per `payload.decisions[]`), `mocs/Projects.md` (per `payload.action_items[]`) |
| Audit events | `meeting-file-written` (full) / `meeting-moc-updated` (moc_only) |
| Action-item cap per project | 20 entries; oldest unchecked dropped first |

## Procedure

1. Compute target path: `meetings/{{date}}-{{slug}}.md`.
2. Read the target path.
   - If `mode == full` and file exists: refuse and surface a "file already exists, use /pm-overwrite" hint. Never silently overwrite. Stop here.
   - If `mode == moc_only` and file exists: proceed to Step 5 (skip Steps 3 and 4).
   - If `mode == moc_only` and file is missing: add `target file missing for moc_only mode` to `errors` and stop — do not proceed to Steps 3–7.
   - If `mode == full` and file does not exist: proceed to Step 3.
3. Read the template at `<vault_root>/templates/meeting-note.md` (paths in this skill are resolved from the vault root). Render it with the payload, filling in all fields:
   - Frontmatter: `type` (fixed: `meeting`), `date`, `project`, `participants` (inline YAML array), `tags` (inline YAML array).
   - Body sections in order: `## Decisions`, `## Action items`, `## Open questions`.
   - Omit a section entirely (heading and body) if the corresponding payload list is empty or absent. Do not render placeholder text such as "TBD" or "N/A".
4. Write the rendered note to `meetings/{{date}}-{{slug}}.md`.
5. Read `mocs/Decisions.md`.
   - If `mocs/Decisions.md` does not exist: create it with just the new `## {{project}}` section containing the new bullet(s). No frontmatter required. Proceed to Step 6.
   - If `mocs/Decisions.md` exists but is unreadable: add `mocs/Decisions.md read error` to `errors` and skip the rest of Step 5 and Step 6.
   - If readable: for each entry in `payload.decisions[]`, locate the `## {{project}}` header (level-2, exact project name match, case-insensitive):
     - If found: insert `- [[meetings/{{date}}-{{slug}}]] — <decision entry>` as a new bullet at the top of that section's list (most-recent first within the session). Bullets within a section are ordered most-recent first by date embedded in the slug.
     - If not found: create a new `## {{project}}` section, insert the bullet(s), then re-sort all level-2 project headers alphabetically (case-insensitive). Preserve any `## Manual notes` section at its original position (do not sort it).
   - If `payload.decisions[]` is empty: still proceed to Step 6 without modifying `mocs/Decisions.md`.
   Write the updated content back to `mocs/Decisions.md` only if at least one bullet was inserted.
6. Read `mocs/Projects.md`.
   - If `mocs/Projects.md` does not exist or is unreadable: do nothing — this is a soft optional update.
   - If readable: for each entry in `payload.action_items[]`, if a `## {{project}}` section exists and contains an `### Action items` subheading:
     - Append `- [ ] <action_item> — owner: <owner>` to the list under `### Action items` (newest at bottom; preserve checkbox state if subsequently edited; never duplicate entries whose action text — the part before ` — owner:` — already exists in the list).
     - Cap the project's action-item list at **20 entries**: if the cap would be exceeded, drop the oldest unchecked entries first (entries with `- [x]` are not dropped).
     - Write the updated content back to `mocs/Projects.md`.
   - If `## {{project}}` is absent, or `### Action items` is absent under it, or `payload.action_items[]` is empty: do nothing to `mocs/Projects.md`.
7. Call `fts_index(path, title, body)` where `path` is `meetings/{{date}}-{{slug}}.md` and `title` is `{{title}}`. For `body`:
   - In `full` mode: use the rendered template content produced in Step 3.
   - In `moc_only` mode: read the existing file at `meetings/{{date}}-{{slug}}.md` to obtain its full content, and use that as `body`.
   If the call fails or times out, add `fts_index <error>` to `errors` and continue — do not roll back any writes.
8. Emit the audit event:
   - In `full` mode: emit `meeting-file-written` with `{ files_written: [<meeting-path>, <moc-files-actually-updated>] }` — include `mocs/Decisions.md` and `mocs/Projects.md` only if each was actually modified.
   - In `moc_only` mode: emit `meeting-moc-updated` with `{ files_written: [<moc-files-actually-updated>] }` — list only the MOC files that were actually written. Do not include the meeting file path.

## Pitfalls

- Never silently overwrite an existing meeting file in `full` mode — refuse with a `/pm-overwrite` hint.
- In `moc_only` mode, if the target file is missing, stop immediately (do not run Steps 3-7).
- Do not render placeholder text ("TBD", "N/A") for empty payload lists — omit the section entirely.
- Never duplicate action items in `mocs/Projects.md`; match on the text before ` — owner:`.
- Do not drop checked (`- [x]`) action items when enforcing the 20-entry cap — drop oldest unchecked only.
- Preserve any `## Manual notes` section at its original position when re-sorting `mocs/Decisions.md`.

## Verification

- File `meetings/{{date}}-{{slug}}.md` exists at the computed path (in `full` mode).
- For each `payload.decisions[]` entry, `mocs/Decisions.md` has a bullet `- [[meetings/{{date}}-{{slug}}]] — <decision entry>` under `## {{project}}`.
- For each `payload.action_items[]` entry whose project section in `mocs/Projects.md` has `### Action items`, the bullet `- [ ] <action_item> — owner: <owner>` was appended; the list length is ≤20.
- Audit event `meeting-file-written` (or `meeting-moc-updated`) was emitted with the actual `files_written` list.
- The full content of the target file was passed to `fts_index` (in both modes), or an `fts_index <error>` was recorded.
