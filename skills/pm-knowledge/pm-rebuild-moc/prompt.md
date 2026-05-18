You are reconstructing a single Map-of-Content (MOC) file from all matching atomic notes in the vault, with a unified-diff preview before any write.

Output **language**: {{lang}}.

---

## Vault layout

- Atomic-note folders are **lowercase**: `decisions/`, `meetings/`, `daily/`. Any additional atomic-note folder follows the same lowercase convention.
- MOC files are **capitalized filenames** under the lowercase `mocs/` folder: `mocs/Decisions.md`, `mocs/Projects.md`, `mocs/People.md`, `mocs/Areas.md`.
- The snapshot history mirror lives at `<vault_root>/_brain/_history/mocs/`.

Paths in the rendered MOC body are **vault-root-relative without the `.md` extension** (e.g., `decisions/2026-05-17-foo`, not `/Users/.../decisions/2026-05-17-foo.md`).

---

## Per-MOC scan and grouping rules

There are four supported MOC names: `Decisions`, `Projects`, `People`, `Areas`. Each has a fixed scan source and a fixed grouping key.

### `Decisions`

- **Scan source**: every file matching `<vault_root>/decisions/*.md`. Subdirectories under `decisions/` are not scanned in v0 — the project keeps decisions flat.
- **Grouping key**: frontmatter `project` field (string). Trim whitespace. Comparison is case-insensitive when merging groups; group display name uses the casing of the first occurrence seen in scan order.
- **Unassigned handling**: a decision with no `project` field, an empty `project`, or `project: null` goes into a group named exactly `Unassigned` (capitalized).
- **Group ordering**: alphabetical case-insensitive by group name, with `Unassigned` always sorted last regardless of alphabetical position. Empty groups (zero entries) are not rendered.

> **Convention note:** the `Unassigned`-last rule above is the authoritative ordering for the Decisions MOC. `pm-add-decision` currently sorts strictly alphabetical with no carve-out and will be aligned to match this rule in a follow-up pass; until then, repeated `pm-add-decision` calls may reorder a freshly rebuilt MOC.

### `Projects`

- **Scan source** (union of three passes, deduplicated by file path):
  1. Every file matching `<vault_root>/meetings/*.md`.
  2. Every file matching `<vault_root>/decisions/*.md`.
  3. Every other atomic note in the vault (any `.md` outside `mocs/`, `templates/`, and `_brain/`) that contains a `project:` frontmatter field.
- Each scanned file contributes **one bullet per unique `project` value it declares**. If a file declares no `project`, it is not rendered (Projects MOC indexes project-tagged work only).
- **Grouping key**: frontmatter `status` field (string). Allowed values: `active`, `paused`, `done`. Any other value, or absence of `status`, maps to the group `unknown`.
- **Group ordering**: fixed sequence `active`, `paused`, `done`, `unknown`. Empty groups are omitted.
- **Per-bullet detail**: the bullet still references the source atomic note (the meeting/decision/note file), not a synthetic project record. If the same atomic note declares multiple projects, it appears once per declared project in the respective project's group — but `Projects.md` is grouped by `status`, not by `project`, so multi-project notes appear once per (project, status) combination in v0.

> **v0 limitation:** `status` is read from each scanned file's own frontmatter, not from a separate project registry. Because meetings and decisions don't normally carry a `status:` field, the Projects MOC in v0 will typically collapse into a single `## unknown` group containing every entry. Treat it as an index of project-tagged files until v1 introduces a `Projects/<slug>.md` project-record schema with explicit `status:` frontmatter.

### `People`

- **Scan source**: every file matching `<vault_root>/meetings/*.md`.
- **Grouping key**: the **full person name** as it appears in the meeting's `participants` frontmatter list, trimmed of leading/trailing whitespace. One level-2 section per unique person. Section heading format is `## <Person Name>` verbatim — preserve case and any diacritics from the source frontmatter. Names that are identical strings after trimming collapse into one section.
- Each meeting file contributes one bullet per unique person listed in its frontmatter `participants` field. If a meeting has no `participants`, it is not rendered. If `participants` is a scalar string rather than a list, treat it as a single-element list (mirroring the `tags`-handling convention from `pm-link-notes`). Empty or blank participant entries are skipped silently.
- A single meeting may appear under multiple person sections if it has multiple participants. Deduplication is by (person, meeting path).
- **Per-section bullet sort**: meeting date descending (most-recent first). Bullets with `undated` sort last within the section in stable input order.
- **Group ordering**: alphabetical Latin `A-Z` first, then Cyrillic `А-Я`. Ties are resolved lexicographically. Empty sections are not rendered.

### `Areas`

- **Scan source**: every atomic `.md` file in the vault outside `mocs/`, `templates/`, and `_brain/`.
- **Grouping key**: frontmatter `area:` value, or `theme:` if `area:` is absent on that file. Files with neither `area:` nor `theme:` are not rendered (the Areas MOC indexes area-tagged content only). Trim whitespace. Comparison is case-insensitive when merging groups; group display name uses the casing of the first occurrence seen in scan order.
- **Group ordering**: alphabetical case-insensitive by group name. Empty groups are omitted.

---

## Frontmatter handling

- The current MOC's frontmatter block is preserved **verbatim** from the existing file. The skill never edits frontmatter fields during a rebuild.
- The `type: moc` field must remain. If the current file lacks frontmatter entirely (e.g., file did not exist or was created without one), the skill emits the canonical frontmatter `---\ntype: moc\n---\n` at the top of the new body.
- The skill does not add or remove other frontmatter fields. If a user has added custom frontmatter (e.g., `aliases:`, `cssclass:`), it is preserved without change.

---

## Header level conventions

- The MOC H1 is always `# {{moc_name}}` (level-1) on its own line, followed by one blank line.
- Group headings are level-2: `## <group_name>`. One blank line between the heading and its first bullet. One blank line between adjacent groups (between the last bullet of group N and the heading of group N+1).
- The preserved `## Manual notes` block uses its existing heading case verbatim (e.g., `## Manual notes`, `## manual notes`, `## MANUAL NOTES`). The skill does not re-case it.
- No level-3 or deeper headings are emitted by the skill. If a preserved `## Manual notes` block contains nested headings (`###`, `####`), those are preserved verbatim inside the block.

---

## Bullet format

```
- [[<path-without-md>]] — <Title>  (<date>)
```

- `<path-without-md>`: vault-root-relative path with the `.md` extension stripped. Example: `decisions/2026-05-17-foo`.
- ` — `: em dash (U+2014) surrounded by single spaces. Not a double-hyphen `--`.
- `<Title>`: the scanned file's H1 heading. If no H1 is found, use the filename slug (basename without `.md`, hyphens replaced by spaces, title-cased).
- `  (<date>)`: two spaces precede the open parenthesis. `<date>` is the ISO date (`YYYY-MM-DD`) detected from the frontmatter `date` field, or from a `YYYY-MM-DD-` filename prefix. If no date is detectable, the literal string `undated` replaces the ISO date.
- One bullet per line. No sub-bullets.
- The `People` MOC uses this same standard bullet form — no person-name prefix on the bullet, since the section heading already names the person.

---

## Bullet ordering within a group

- Bullets are sorted by detected date **descending** (most-recent first).
- Bullets with `undated` sort last within their group, in stable input order (insertion order from the scan pass).
- For the `Projects` MOC: within each status group, bullets are sorted by date descending across all underlying atomic notes (regardless of which `project` value they reference).
- For the `People` MOC: within each person section, bullets are sorted by date descending across all meetings where that person participated.

---

## `## Manual notes` preservation

This is the load-bearing safety guarantee of the skill.

### Detection

Search the current MOC content for a level-2 heading matching the case-insensitive regex `^##\s+[Mm]anual\s+[Nn]otes\s*$` on a line by itself. Accepted variants include `## Manual notes`, `## manual notes`, `## Manual Notes`, `## MANUAL NOTES`.

### Capture boundary

The captured block runs from the matched heading line through the end of the file. Inside this block, any subsequent `##` heading is treated as part of the manual notes (not a boundary) — once the `## Manual notes` heading is seen, everything that follows belongs to the user.

### Re-insertion

The captured block is appended verbatim at the very end of the new MOC body, after all grouped sections. The block's leading newlines, trailing whitespace, heading casing, bullet style, and any nested headings are preserved exactly. The skill never reformats, re-cases, or re-orders anything inside the manual-notes block.

### Heading-case mismatch warning (non-fatal)

If the detected heading is not the canonical `## Manual notes` (e.g., `## manual notes`, `## MANUAL NOTES`, `## Manual Notes`), record `manual-notes-heading-case-mismatch: <original_case>` in `errors` as a non-fatal warning and continue the rebuild. The user's original heading case is preserved verbatim in the output; the warning is informational only and mirrors the convention used by `pm-link-notes` for `related-heading-case-mismatch`.

### Failure modes (all fatal — abort without writing)

- Multiple `## Manual notes` headings detected (ambiguous capture boundary): emit `manual-notes-extraction-failed: multiple Manual notes headings detected`.
- Heading detected but capture extends to zero bytes (file ends immediately after heading with no body): treated as a valid empty block — not an error. The heading line is still preserved.
- File read or decode error during extraction: emit `manual-notes-extraction-failed: <reason>`.

On any fatal failure: emit audit `moc-rebuilt` with `written: false`, `errors: ['manual-notes-extraction-failed: ...']`, and stop. Do not snapshot. Do not write.

---

## Empty-MOC rendering

If the scan returns zero matching entries (no decisions, no projects, no participants, no areas) **and** no `## Manual notes` block was preserved:

```
---
type: moc
---
# {{moc_name}}

(empty)
```

If zero entries but a `## Manual notes` block was preserved:

```
---
type: moc
---
# {{moc_name}}

(empty)

## Manual notes

<preserved block body>
```

The `(empty)` marker is omitted when at least one grouped section is rendered.

---

## Unified-diff preview format

The Phase 1 `diff` field is a unified-diff string produced from the current MOC content vs. the rendered new content. Format follows the standard `difflib.unified_diff` output:

```
--- mocs/<moc_name>.md (current)
+++ mocs/<moc_name>.md (rebuilt)
@@ -<old_start>,<old_count> +<new_start>,<new_count> @@
 <context line>
-<removed line>
+<added line>
 <context line>
@@ ...
```

- File headers use the exact strings `mocs/<moc_name>.md (current)` and `mocs/<moc_name>.md (rebuilt)`.
- Context is 3 lines (`n=3`) above and below each change region.
- Trailing newlines are not stripped from input — the diff reflects the file as it would be written to disk.
- If the current MOC did not exist, the `--- mocs/<moc_name>.md (current)` side compares against the empty string; the entire new body shows as `+` lines.
- If the rendered body is byte-identical to the current file, the diff is the literal string `(no changes)` and Phase 1 still returns a payload but with `confirmation_token` computed normally — Phase 2 with a matching token would be a no-op write (and the skill skips the actual file write but still emits the audit event with `written: false` and `errors: ['no-op: rebuilt body identical to current content']`).

---

## Preview output format

When Phase 1 completes (no write), output the following human-readable summary to the caller before returning the JSON payload:

```
Rebuilding MOC: mocs/<moc_name>.md
Entries grouped: <grouped_count>
Manual notes preserved: yes | no

Diff preview:
<unified diff text, truncated to 80 lines if longer; append "... (<N> more lines)" when truncated>

To apply, re-invoke with:
  approve: true
  confirmation_token: <16-char hex>
```

- The diff is shown verbatim up to 80 lines. Beyond 80, append a single truncation marker — do not silently drop content.
- If `errors` is non-empty, append after the diff:
  ```
  Warnings: <error1>; <error2>
  ```

---

## Confirmation token format

```
confirmation_token = sha256( moc_name + "\n" + <canonical new body> )[:16]
```

- `moc_name`: one of `Decisions`, `Projects`, `People`, `Areas` (case-sensitive).
- `<canonical new body>`: the full rendered file content from Step 5 of SKILL.md, byte-for-byte as it would be written to disk (frontmatter through preserved manual-notes block, inclusive of trailing newline).
- The `\n` line-feed separator prevents collisions between distinct MOC names and content combinations.
- Truncate to the first 16 hexadecimal characters of the SHA-256 digest.

---

## Output JSON shape

After all preview/write/audit work completes, return exactly one JSON object. There are four shapes.

**Phase 1 (preview, no write):**
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
  "files_written": [],
  "errors": []
}
```

**Phase 2 success (write completed):**
```json
{
  "phase": 2,
  "action": "rebuild",
  "moc_name": "<moc_name>",
  "grouped_count": <int>,
  "manual_notes_preserved": true | false,
  "tok_in": <int>,
  "tok_out": <int>,
  "files_written": ["mocs/<moc_name>.md"],
  "errors": []
}
```

**Phase 2 mismatch (confirmation_token did not match recomputed token):**
```json
{
  "phase": 2,
  "action": "rebuild",
  "moc_name": "<moc_name>",
  "tok_in": <int>,
  "tok_out": <int>,
  "files_written": [],
  "errors": ["confirmation_token mismatch — re-run without approve:true to generate a fresh preview"]
}
```

**Stop-without-write (any fatal error in Steps 1–2):**
```json
{
  "phase": 1,
  "action": "rebuild",
  "moc_name": "<moc_name or 'invalid'>",
  "tok_in": <int>,
  "tok_out": <int>,
  "files_written": [],
  "errors": ["<reason>"]
}
```

Rules:
- Always emit the JSON object, even when stopping on error.
- An entry in `errors` does not suppress the JSON line.
- `files_written` contains only paths actually written during this invocation. The snapshot file under `_brain/_history/` is not listed in `files_written`.
- `tok_in` and `tok_out` reflect token counts for this invocation only.
- The `phase` field is always present (1 for preview or Phase 1 abort; 2 for write, write-failure, or Phase 2 abort).

**Error label reference (distinct keys):**

| Key | When emitted |
|-----|-------------|
| `invalid moc_name: <value> — must be one of Decisions, Projects, People, Areas` | Input validation failed (Step 1) |
| `current MOC unreadable: <reason>` | The existing MOC file could not be read (Step 1) |
| `manual-notes-extraction-failed: <reason>` | `## Manual notes` capture failed (Step 2) |
| `manual-notes-heading-case-mismatch: <original_case>` | Non-fatal: `## Manual notes` heading detected with non-canonical casing (Step 2). Preserved verbatim in output. |
| `read-failed: <path>: <reason>` | Non-fatal: an individual scan file could not be read (Step 3) |
| `confirmation_token mismatch — re-run without approve:true to generate a fresh preview` | Token provided in Phase 2 did not match the recomputed token (Step 6b) |
| `no-op: rebuilt body identical to current content` | Phase 2 reached write step but the new body matches the current file — no write performed |
