You are writing an atomic decision note to the vault and updating MOC indexes.

Output **language**: {{lang}}.

---

## Slug rule

The slug is computed by `pm-workflow.pm-decision` before handoff. Verify it on receipt:

- All lowercase, ASCII only.
- Cyrillic characters are transliterated to Latin using GOST 7.79 System B (e.g., `с → s`, `ш → sh`, `щ → shch`, `ж → zh`, `ч → ch`, `х → kh`, `ц → ts`, `ю → yu`, `я → ya`).
- Any non-alphanumeric run (spaces, punctuation) is collapsed to a single `-`.
- Leading and trailing dashes are trimmed.
- Maximum length: **60 characters**. If the 60-char boundary falls mid-word, trim back to the previous `-`.

If the received slug does not conform, re-derive it from the title using the rules above before computing the file path.

If the result is empty after trimming (e.g., the title contained only punctuation or untransliteratable characters), refuse the operation and emit `errors: ['slug resolved to empty string — provide an explicit slug']`. Do not fall back to an opaque hash or a date-only filename.

Examples:
- "Switch payment provider to Stripe" → `switch-payment-provider-to-stripe`
- "Сократить онбординг до 3 шагов" → `sokratit-onbording-do-3-shagov`

---

## Conflict resolution (duplicate slug)

Target path: `decisions/{{date}}-{{slug}}.md`.

- **Default flow**: if the file already exists, refuse the write. Return a user-facing message: `"File decisions/{{date}}-{{slug}}.md already exists. Use /pm-overwrite to replace it."` Do not write the file. Do not append a `-2` suffix automatically.
- **After /pm-overwrite**: the caller re-invokes with an explicit overwrite flag. In that case, overwrite the existing file. The `-2` suffix is never used in normal operation.

---

## Template rendering

Render `templates/decision-note.md` exactly. Fill each placeholder from the payload:

| Placeholder | Source field |
|---|---|
| `{{date}}` | `payload.date` (ISO `YYYY-MM-DD`) |
| `{{project}}` | `payload.project` |
| `{{tags}}` | `payload.tags` joined by `, ` |
| `{{owner}}` | `payload.owner` |
| `{{title}}` | `payload.title` (used as H1) |
| `{{context}}` | `payload.context` |
| `{{options}}` | `payload.options` rendered as a bullet list |
| `{{decision}}` | `payload.decision` |
| `{{rationale}}` | `payload.rationale` |
| `{{consequences}}` | `payload.consequences` |
| `{{links}}` | `payload.links` rendered as a bullet list of wikilinks |

Omit a section entirely — heading and body — if the corresponding payload field is empty, null, or absent. Do not render placeholder text such as "TBD" or "N/A".

---

## MOC update grammar — `mocs/Decisions.md`

File structure expected:

```
## ProjectAlpha

- [[decisions/2026-03-10-some-slug]] — Some decision title
- [[decisions/2026-01-05-another-slug]] — Another decision title

## ProjectBeta

- [[decisions/2026-04-01-yet-another]] — Yet another decision

## Manual notes

...preserved verbatim...
```

**Insertion rules:**

1. Detect project headers with the regex `^## (?P<project>[^\n]+)$`. The `## Manual notes` header is excluded from all sorting and insertion logic — treat it as an immovable block.
2. If a matching `## {{project}}` header exists (case-insensitive match on the project name):
   - After the header line and any single blank line that follows it, insert the new bullet `- [[decisions/{{date}}-{{slug}}]] — {{title}}` as the first item in the section's bullet list. Bullets within a section are ordered most-recent first (by `date` field embedded in the slug — newer dates float to the top).
3. If no matching header exists:
   - Create a new section: `## {{project}}\n\n- [[decisions/{{date}}-{{slug}}]] — {{title}}\n`.
   - Re-sort all project sections alphabetically (case-insensitive) by their header name. When re-sorting, each section's body — all lines from its `##` header through the line preceding the next `##` header — moves as an indivisible unit. `## Manual notes` is anchored to its current position and is not re-sorted.
4. Blank lines between sections: keep exactly one blank line between adjacent sections.
5. If the file is empty or contains only frontmatter, treat the bulleted-list region as empty and append the new `## {{project}}` section as the file's first content section.

---

## MOC update grammar — `mocs/Projects.md`

File structure assumed (per-project sections):

```
## ProjectAlpha

### Overview
...

### Recent decisions

- [[decisions/2026-04-15-last-decision]] — Last decision title
- [[decisions/2026-02-10-earlier-decision]] — Earlier decision title

### OKRs
...
```

**Insertion rules:**

1. If `mocs/Projects.md` does not exist or is unreadable, do nothing — this is a soft optional update.
2. Locate `## {{project}}` (level-2, case-insensitive match).
   - If absent: do nothing. Do not create a new project section.
3. Within that section, locate `### Recent decisions` (level-3).
   - If absent: do nothing. Do not create the subheading.
4. If both exist:
   - Prepend `- [[decisions/{{date}}-{{slug}}]] — {{title}}` to the bullet list under `### Recent decisions` (most-recent first).
   - Cap the list at **5 entries**: if insertion would exceed 5, drop the oldest (last) entry.

---

## Output JSON

After all writes and index calls complete, return exactly one JSON line.

**In `full` mode** — emit event name `decision-file-written`:

```json
{"event": "decision-file-written", "tok_in": <int>, "tok_out": <int>, "files_written": ["decisions/{{date}}-{{slug}}.md", "mocs/Decisions.md"], "errors": []}
```

- Always include the decision file path as the first entry in `files_written`.
- Include `"mocs/Decisions.md"` only if it was actually written.
- Include `"mocs/Projects.md"` only if it was actually modified.

**In `moc_only` mode** — emit event name `decision-moc-updated`:

```json
{"event": "decision-moc-updated", "tok_in": <int>, "tok_out": <int>, "files_written": ["mocs/Decisions.md"], "errors": []}
```

- Do not include the decision file path in `files_written` — no decision file is written in this mode.
- Include `"mocs/Decisions.md"` only if it was actually written.
- Include `"mocs/Projects.md"` only if it was actually modified.

**Both modes:**

- Populate `errors` with a string description for any step that failed (e.g., `fts_index` timeout, file write error). An entry in `errors` does not suppress the JSON line — always emit it.
