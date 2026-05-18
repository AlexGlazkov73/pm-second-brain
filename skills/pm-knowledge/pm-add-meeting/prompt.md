You are writing an atomic meeting note to the vault and updating MOC indexes.

Output **language**: {{lang}}.

---

## Project inference

Project inference is meeting-specific; the decision skill assumes `project` is present in the payload, while meetings often lack an explicit project label.

Extract `project` from the payload in this order:

1. Explicit mention of a project name in the user's message or payload.
2. Most recent project referenced in the current conversation context.
3. First project in `mocs/Projects.md` whose `## <project>` section overlaps with any participant or topic mentioned in the meeting context.
4. If no confident match found after steps 1–3: ask the user a single clarifying question. Do not guess.

---

## Slug rule

The slug may be pre-computed by the caller or derived here. Verify it on receipt using the rules below; re-derive from the title if it does not conform.

The slug derives from the meeting title. Compute it as follows:

- All lowercase, ASCII only.
- Cyrillic characters are transliterated to Latin using GOST 7.79 System B (e.g., `с → s`, `ш → sh`, `щ → shch`, `ж → zh`, `ч → ch`, `х → kh`, `ц → ts`, `ю → yu`, `я → ya`).
- Any non-alphanumeric run (spaces, punctuation) is collapsed to a single `-`.
- Leading and trailing dashes are trimmed.
- Maximum length: **60 characters**. If the 60-char boundary falls mid-word, trim back to the previous `-`.

If the received slug does not conform, re-derive it from the title using the rules above before computing the file path.

If the result is empty after trimming (e.g., the title contained only punctuation or untransliteratable characters), refuse the operation and emit `errors: ['slug resolved to empty string — provide an explicit slug']`. Do not fall back to an opaque hash or a date-only filename.

Examples:
- "Sprint planning Q3" → `sprint-planning-q3`
- "Ретро по продукту" → `retro-po-produktu`

---

## Conflict resolution (duplicate slug)

Target path: `meetings/{{date}}-{{slug}}.md`.

- **Default flow**: if the file already exists, refuse the write. Return a user-facing message: `"File meetings/{{date}}-{{slug}}.md already exists. Use /pm-overwrite to replace it."` Do not write the file. Do not append a `-2` suffix automatically.
- **After /pm-overwrite**: the caller re-invokes with an explicit overwrite flag. In that case, overwrite the existing file. The `-2` suffix is never used in normal operation.

---

## Participant deduplication

Before populating `participants[]`:

1. Normalize each entry to "First Last" form (trim whitespace, collapse internal spaces to one). Preserve original Cyrillic spelling if present (e.g., "Алексей Глазков" stays as-is). Strip honorific prefixes (`Dr.`, `Prof.`, `г-н`, `г-жа`) before normalization. Convert inverted `Lastname, Firstname` to `Firstname Lastname`.
2. Deduplicate case-insensitively after normalization (e.g., "alex ivanov" and "Alex Ivanov" are the same person — keep the best-cased form).
3. Drop entries that are only role labels without a name attached (e.g., "PM", "designer", "dev", "QA"). If a role label has a name attached (e.g., "PM Алексей"), keep it normalized to the name portion.
4. Never invent participants. If the input provides no participants, leave `participants: []` — do not fill in the meeting organizer or any inferred names.

---

## Action-item owner inference

For each item in `action_items[]`:

1. Scan the action-item string for owner-signal patterns:
   - `<Name> will <verb> ...` (e.g., "Алексей will set up staging")
   - `<Name> takes <noun>` (e.g., "Maria takes the follow-up")
   - `owner: <Name>` (e.g., "owner: Sergei")
   - `@<Name>` (e.g., "@Ivan")
2. Match the extracted name against the deduplicated `participants[]` list (case-insensitive, partial match on last name or first name acceptable if unambiguous).
   - If partial matching against first name or last name produces more than one candidate participant, treat the result as no match and set `owner: unassigned`.
   - If an entry in `participants[]` has no whitespace after normalization (single token), treat the whole token as both first and last name for matching purposes.
3. If a match is found: set `owner` to the matched participant's canonical name.
4. If no match is found, or the extracted name is not in `participants[]`: set `owner: unassigned`.
5. Never guess an owner not present in `participants[]`. Do not assign ownership based on topic or role alone.
6. Before rendering the output line, strip any existing `— owner: <text>` suffix from `<action_item_text>` to avoid double-suffixing.

The rendered line in `mocs/Projects.md` is: `- [ ] <action_item_text> — owner: <owner>`

---

## "Decisions" subsection inclusion criteria

Only include a statement in `decisions[]` if it contains explicit decision wording. Accepted trigger phrases:

- `we decided` / `we've decided`
- `the call is`
- `решили` (Russian: "we decided")
- `решение —` (Russian: "decision is")
- `we agreed` / `we've agreed`
- `consensus is`

After a trigger phrase matches, apply a secondary hedging check: if the sentence contains `to consider`, `might`, `could`, `should consider`, or `думаем о том` as a continuation following or near the trigger phrase, treat it as hedged and exclude it.

Reject hedged or exploratory statements. Examples of what to exclude:

- "we might move the deadline" — hedged
- "we should consider switching providers" — speculative
- "it could be worth trying" — exploratory
- "мы думаем о том, чтобы..." — tentative

If a statement passes the inclusion criterion, extract a concise title for the `decisions[]` entry (one short sentence or noun phrase). That title is used both in the meeting note body under `## Decisions` and as the bullet label in `mocs/Decisions.md`.

---

## Template rendering

Render `templates/meeting-note.md` exactly. Fill each placeholder from the payload:

| Placeholder | Source field |
|---|---|
| `{{date}}` | `payload.date` (ISO `YYYY-MM-DD`) |
| `{{project}}` | `payload.project` (single string value) |
| `{{participants}}` | `payload.participants[]` as inline YAML array, comma-separated |
| `{{tags}}` | `payload.tags[]` as inline YAML array, comma-separated |
| `{{title}}` | `payload.title` (used as H1) |
| `{{decisions}}` | `payload.decisions[]` rendered as a bullet list |
| `{{action_items}}` | `payload.action_items[]` rendered as a checkbox list (`- [ ] ...`) |
| `{{open_questions}}` | `payload.open_questions[]` rendered as a bullet list |

Omit a section entirely — heading and body — if the corresponding payload list is empty, null, or absent. Do not render placeholder text such as "TBD" or "N/A".

`project` is always a single string, never a list. `participants` and `tags` must be rendered as inline YAML arrays in the frontmatter (e.g., `participants: [Alice, Bob]`).

If `payload.tags[]` is empty, render `tags: []` (keep the key; do not omit the frontmatter line). The same applies to `participants: []`.

---

## MOC update grammar — `mocs/Decisions.md`

File structure expected:

```
## ProjectAlpha

- [[meetings/2026-03-10-some-slug]] — Some decision title
- [[meetings/2026-01-05-another-slug]] — Another decision title

## ProjectBeta

- [[meetings/2026-04-01-yet-another]] — Yet another decision

## Manual notes

...preserved verbatim...
```

**Insertion rules:**

1. Detect project headers with the regex `^## (?P<project>[^\n]+)$`. The `## Manual notes` header is excluded from all sorting and insertion logic — treat it as an immovable block.
2. If a matching `## {{project}}` header exists (case-insensitive match on the project name):
   - After the header line and any single blank line that follows it, insert the new bullet `- [[meetings/{{date}}-{{slug}}]] — <decision title>` as the first item in the section's bullet list. Bullets within a section are ordered most-recent first (by `date` field embedded in the slug — newer dates float to the top).
3. If no matching header exists:
   - Create a new section: `## {{project}}\n\n- [[meetings/{{date}}-{{slug}}]] — <decision title>\n`.
   - Re-sort all project sections alphabetically (case-insensitive) by their header name. When re-sorting, each section's body — all lines from its `##` header through the line preceding the next `##` header — moves as an indivisible unit. `## Manual notes` is anchored to its current position and is not re-sorted.
4. If `payload.decisions[]` contains multiple entries, insert each as a separate bullet. All new bullets are inserted above pre-existing bullets for that project (most-recent first within the session, then oldest-date pre-existing bullets below). Before inserting, deduplicate new bullets within the current payload: if two entries in `payload.decisions[]` produce identical bullet text, insert only one bullet.
5. Blank lines between sections: keep exactly one blank line between adjacent sections.
6. If the file is empty or contains only frontmatter, treat the bulleted-list region as empty and append the new `## {{project}}` section as the file's first content section.
7. If `payload.decisions[]` is empty, do not modify `mocs/Decisions.md`.

---

## MOC update grammar — `mocs/Projects.md`

File structure assumed (per-project sections):

```
## ProjectAlpha

### Overview
...

### Action items

- [ ] Set up staging environment — owner: Ivan
- [x] Send stakeholder update — owner: Maria

### OKRs
...
```

**Insertion rules:**

1. If `mocs/Projects.md` does not exist or is unreadable, do nothing — this is a soft optional update.
2. Locate `## {{project}}` (level-2, case-insensitive match).
   - If absent: do nothing. Do not create a new project section.
3. Within that section, locate `### Action items` (level-3).
   - If absent: do nothing. Do not create the subheading.
4. If both exist and `payload.action_items[]` is non-empty:
   - Append `- [ ] <action_item_text> — owner: <owner>` to the list under `### Action items` (append at the bottom of the existing list).
   - Before appending, check for action-text duplicates: if a line whose text portion (the part before ` — owner:`) exactly matches the new entry's text portion already exists in the list, skip the new entry regardless of the owner value.
   - Cap the list at **20 entries**: if insertion would exceed 20, drop the oldest unchecked entries (lines matching `- [ ] ...`) first. Checked entries (lines matching `- [x] ...`) are never dropped by the cap.

---

## Output JSON

After all writes and index calls complete, return exactly one JSON line.

**In `full` mode** — emit event name `meeting-file-written`:

```json
{"event": "meeting-file-written", "tok_in": <int>, "tok_out": <int>, "files_written": ["meetings/2026-05-18-sprint-planning-q3.md", "mocs/Decisions.md"], "errors": []}
```

- Always include the meeting file path as the first entry in `files_written`.
- Include `"mocs/Decisions.md"` only if it was actually written (i.e., `payload.decisions[]` was non-empty and the write succeeded).
- Include `"mocs/Projects.md"` only if it was actually modified (i.e., `payload.action_items[]` was non-empty and the section existed and the write succeeded).

**In `moc_only` mode** — emit event name `meeting-moc-updated`:

```json
{"event": "meeting-moc-updated", "tok_in": <int>, "tok_out": <int>, "files_written": ["mocs/Decisions.md", "mocs/Projects.md"], "errors": []}
```

- Do not include the meeting file path in `files_written` — no meeting file is written in this mode.
- Include each MOC file only if it was actually written.

**Rule: include a file in `files_written` only if it was actually written during this invocation.**

**Both modes:**

- Populate `errors` with a string description for any step that failed (e.g., `fts_index timeout`, `mocs/Decisions.md read error`). An entry in `errors` does not suppress the JSON line — always emit it.
