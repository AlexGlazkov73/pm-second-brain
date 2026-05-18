---
name: pm-rebuild-moc
description: Reconstruct a single MOC file from all matching atomic notes in the vault. Diff-preview before write.
allowed_tools: ["Read", "Write", "fts_search"]
model_preference: "claude-sonnet-4-6"
inputs: { moc_name: "Decisions | Projects | People | Areas", approve: "false | true — default: false", confirmation_token: "token from Phase 1; required when approve is true" }
---

# pm-rebuild-moc

## Overview

Two-phase stateless skill.

- **Phase 1** (`approve: false`, default): scan the vault, group entries per the MOC's grouping rule, render the new MOC body, build a unified-diff preview against the current file, and return without writing.
- **Phase 2** (`approve: true`): caller re-invokes with the same `moc_name` and the `confirmation_token` from Phase 1. The skill re-runs the scan, recomputes the token, validates it against the caller's token, snapshots the current MOC, and writes the new content.

The `confirmation_token` is `SHA256(moc_name + "\n" + <canonical new body>)` truncated to 16 hex characters. Re-running the scan in Phase 2 and recomputing the token ensures the write always reflects the current vault state, and the equality check prevents a stale approval from being applied to a changed candidate set.

Never write without going through Phase 1 first and receiving an explicit `approve: true` with a matching `confirmation_token`. If `confirmation_token` is absent or mismatched in Phase 2, emit `errors: ['confirmation_token mismatch — re-run without approve:true to generate a fresh preview']` and stop without writing.

---

## Steps

### Step 1 — Validate input and read current MOC

The `moc_name` must be one of: `Decisions`, `Projects`, `People`, `Areas`. Match is case-sensitive.

- If `moc_name` is missing, empty, or not one of the four allowed values: emit audit `moc-rebuilt` with `errors: ['invalid moc_name: <value> — must be one of Decisions, Projects, People, Areas']`, `written: false`. Stop.
- Compute the MOC path: `mocs/{{moc_name}}.md` (capitalized filename under the lowercase `mocs/` folder).
- Attempt to read `<vault_root>/mocs/{{moc_name}}.md`.
  - If the file does not exist: treat the current content as an empty MOC body (no `## Manual notes` section, no existing groups). Proceed to Step 2. The rebuild will create the file in Phase 2.
  - If the file exists but is unreadable (permission error, decode error): emit audit `moc-rebuilt` with `errors: ['current MOC unreadable: <reason>']`, `written: false`. Stop.
- Store the raw current content for use in Steps 4 and 5.

### Step 2 — Extract and preserve `## Manual notes`

Scan the current MOC content for a level-2 heading matching the regex `^##\s+[Mm]anual\s+[Nn]otes\s*$` on a line by itself (case-insensitive on the words `Manual notes`).

- If a matching heading is found: capture the block from that heading line through the end of the file. The capture is verbatim — preserve heading casing, blank lines, bullets, prose, and any nested headings inside the block.
- If the file contains an H1 line after the heading (unusual in MOC bodies), the capture still extends to end-of-file; H1 is not treated as a boundary inside the manual-notes block.
- If no matching heading is found: set the preserved block to the empty string. This is not an error.
- If extraction fails for any other reason (regex engine error, ambiguous structure such as multiple `## Manual notes` headings): emit audit `moc-rebuilt` with `errors: ['manual-notes-extraction-failed: <reason>']`, `written: false`. Stop without proceeding to Step 3.
- If the detected heading is not the canonical `## Manual notes` (e.g., `## manual notes`, `## MANUAL NOTES`, `## Manual Notes`), record `manual-notes-heading-case-mismatch: <original_case>` in `errors` as a non-fatal warning and continue. Preserve the user's original heading case verbatim in the output — the warning is informational only and does not abort the rebuild.

Set `manual_notes_preserved = (preserved block is non-empty)` for the audit payload.

### Step 3 — Scan the vault for entries

Apply the per-MOC scan rule (full grammar in `prompt.md`):

- **Decisions** — scan `<vault_root>/decisions/*.md`. Read each file's frontmatter.
- **Projects** — scan `<vault_root>/meetings/*.md` and `<vault_root>/decisions/*.md`; additionally collect any atomic note across the vault that has a `project:` frontmatter field. Aggregate unique `project` values.
- **People** — scan `<vault_root>/meetings/*.md`. Read each file's `participants` frontmatter (list of person names).
- **Areas** — scan all atomic notes across the vault (`decisions/`, `meetings/`, `daily/`, and any other note folders). Read each file's `area:` or `theme:` frontmatter field.

All scans across all four MOCs exclude these paths: `mocs/`, `templates/`, `_brain/`, and any path under them. These directories are never read as atomic notes.

Folder-casing convention: atomic-note folders are lowercase (`decisions/`, `meetings/`, `daily/`); MOC filenames are capitalized under `mocs/` (`Decisions.md`, `Projects.md`, `People.md`, `Areas.md`).

For each matched entry, collect: vault-root-relative path (without `.md`), H1 heading (or filename slug fallback), date (from frontmatter `date` field or `YYYY-MM-DD-` filename prefix; `null` if undetectable), and the grouping key per the MOC rule.

On a single file read failure: record `read-failed: <path>: <reason>` in `errors` as a non-fatal warning and continue. If the scan returns zero entries: proceed with an empty grouped section set (the rendered body will contain only the H1, optional `(empty)` marker, and the preserved `## Manual notes` block). This is not an error.

### Step 4 — Group entries

Apply the per-MOC grouping rule (full grammar in `prompt.md`):

- **Decisions** — group by frontmatter `project` value (decisions without `project` → `## Unassigned`).
- **Projects** — group by each scanned file's own frontmatter `status` field (`active`, `paused`, `done`); entries without `status` → `## unknown`. **v0 limitation:** because most meetings and decisions don't carry `status`, the `Projects.md` rebuild in v0 will typically yield a single `## unknown` group containing every entry. Use this MOC primarily as an index of project-tagged files until a project-record schema (e.g., `Projects/<slug>.md` with `status:` frontmatter) is introduced in v1.
- **People** — group by full person name (the exact value from the `participants` frontmatter list, trimmed of leading/trailing whitespace). One level-2 section per unique person. Section headings sort alphabetically: Latin `A-Z` first, then Cyrillic `А-Я`, ties resolved lexicographically. Names that are identical strings after trimming collapse into one section. Empty or blank participant entries are skipped. Each meeting may appear under multiple person sections if it has multiple participants.
- **Areas** — group by `area:` value (or `theme:` if `area:` is absent on the entry).

Within each group, sort bullets by date descending. Entries with no detectable date sort last within their group, in stable input order.

### Step 5 — Render new MOC body

Render the new MOC body in this exact structure:

1. Preserve the original frontmatter block verbatim from the current MOC. If the current MOC has no frontmatter (e.g., file did not exist), emit the canonical frontmatter `---\ntype: moc\n---\n`.
2. H1 heading: `# {{moc_name}}` (always emit; one blank line after).
3. If any groups exist: emit each group as a level-2 heading `## <group_name>`, one blank line, the sorted bullets, one blank line between groups. Group ordering is alphabetical case-insensitive by group name, **except** for the Projects MOC where the fixed order is `active`, `paused`, `done`, `unknown` (omit any group with zero entries). For Decisions, the special `Unassigned` group sorts to the end regardless of alphabetical order.
4. If no groups exist after Step 4: emit a single line `(empty)` followed by one blank line.
5. Append the preserved `## Manual notes` block verbatim at the very end. The block begins exactly as captured in Step 2 (including its heading line and any blank lines that immediately followed it). If the preserved block is the empty string, append nothing.

Bullet format under each group heading:
```
- [[<relative_path_without_md>]] — <H1 or filename slug>  (<date>)
```

Where `<date>` is the ISO date (`YYYY-MM-DD`) or the literal string `undated` if no date was detected. Two spaces precede the date parenthetical to match the alignment used elsewhere in the project.

### Step 6 — Build diff preview and conditional write

#### 6a — Build unified diff (both phases)

Compute the unified diff between the current MOC content (or an empty string if the file did not exist) and the rendered new content. Use the standard unified-diff format with `---` and `+++` file headers, 3 lines of context, and `@@ ... @@` hunk markers. The diff render format and exact header strings are specified in `prompt.md`.

Count the grouped entries (`grouped_count` = total bullets emitted across all groups in the new body).

Compute `confirmation_token`:
```
SHA256(moc_name + "\n" + <canonical new body>)
```
Truncate to 16 hex characters. The `<canonical new body>` is the full rendered content from Step 5 (frontmatter through preserved manual-notes block, inclusive), as written would be on disk.

Return the Phase 1 payload without writing to disk:

```json
{
  "phase": 1,
  "action": "rebuild",
  "moc_name": "<moc_name>",
  "grouped_count": <int>,
  "manual_notes_preserved": true | false,
  "diff": "<unified diff text>",
  "confirmation_token": "<16-char hex>",
  "tok_in": <int>,
  "tok_out": <int>,
  "errors": [...]
}
```

If `approve: false` (or absent): stop here. Do not snapshot. Do not write.

#### 6b — Snapshot and write (Phase 2 only, when `approve: true`)

Triggered only when `approve: true` is present in the invocation.

1. Re-run Steps 1–5 to obtain the current candidate set and rendered new body. Recompute `confirmation_token` from the fresh body.
2. Compare against the caller-supplied `confirmation_token`. If mismatch: record `confirmation_token mismatch — re-run without approve:true to generate a fresh preview` in `errors` and stop without writing. Do not snapshot.
3. If the current MOC file exists: snapshot it via the history helper. The snapshot path is `_brain/_history/mocs/{{moc_name}}-<ts>.md`, where `<ts>` is `YYYYMMDD-HHMMSS` in local time (the format used by `history.snapshot`). If the file does not exist (first-time rebuild), skip the snapshot step.
4. Write the new rendered body to `mocs/{{moc_name}}.md`, replacing the file's full contents.

### Step 7 — Emit audit

Emit audit event `moc-rebuilt` with the payload:

```json
{
  "moc_name": "<moc_name>",
  "grouped_count": <int>,
  "manual_notes_preserved": true | false,
  "written": true | false,
  "errors": [...]
}
```

- On Phase 1 (preview-only): `written: false`. `grouped_count` and `manual_notes_preserved` reflect the rendered preview.
- On Phase 2 success: `written: true`. `grouped_count` and `manual_notes_preserved` reflect the actually-written body.
- On stop-without-write at any step: `written: false`. `errors` contains the reason(s).
- Always emit this event, even on errors.

---

## Safety

- Always snapshot the current MOC before write. The only exception is first-time creation, where the file does not exist and there is nothing to snapshot.
- Never lose `## Manual notes` content. If extraction fails (Step 2), abort with `manual-notes-extraction-failed` and surface the reason — do not proceed to render or write.
- Never write in Phase 1. Phase 1 returns the diff and the confirmation token only.
- Never write when the confirmation token mismatches in Phase 2. Re-discovery has already detected vault drift; force the caller to re-preview.
- Never touch any file outside `mocs/{{moc_name}}.md` and the snapshot under `_brain/_history/mocs/`.
