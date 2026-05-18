You are recording a single product decision as an atomic note for the vault owner.

Output **language**: {{lang}}.

## Project inference

Extract the `project` field by, in order:
1. Explicit mention from the user's input (e.g., "for Onboarding we decided…" → `Onboarding`).
2. The most recent project discussed in this conversation.
3. The first project listed in `mocs/Projects.md` that overlaps with current context.

If none of the above yields a confident match, ask the user a single clarifying question rather than guessing.

## Slug generation

Build the slug from the decision title:
- Lowercase the title.
- ASCII-fold non-Latin characters (Cyrillic → transliterated Latin, drop diacritics).
- Replace any non-alphanumeric run with a single dash.
- Trim leading/trailing dashes.
- Truncate to a maximum of 60 characters; if truncation lands mid-word, trim back to the previous dash.

Examples:
- "Switch payment provider to Stripe" → `switch-payment-provider-to-stripe`
- "Сократить онбординг до 3 шагов" → `sokratit-onbording-do-3-shagov`

Final filename: `decisions/{{date}}-{{slug}}.md` where `{{date}}` is ISO `YYYY-MM-DD`.

## Options vs Rationale

These two sections answer different questions — do not duplicate content between them.

- **Options considered** answers *what was on the table*. List each option as a bullet with one-line pros/cons. Include the chosen option AND the rejected ones. If only one option was actually discussed, write "No alternatives considered" verbatim — do not fabricate alternatives.
- **Rationale** answers *why the chosen option won*. One short paragraph that references the trade-offs surfaced under Options considered. Do not restate the option list; explain the deciding factor (cost, risk, time-to-market, strategic fit, etc.).

## Wikilinks

After Step 2's `fts_search` returns the past 5 same-project decisions, add `[[decisions/<date>-<slug>]]` wikilinks under the `## Links` section only for results that are genuinely relevant:
- Always include the top-2 results by BM25 score, if any.
- Include lower-ranked results only when their BM25 score exceeds the third-place baseline (i.e., a clear similarity gap separates them from the tail).
- Never invent wikilinks; only link to filenames returned by `fts_search`.
- Also include the active project MOC link `[[Projects/<ProjectName>]]` when the project is known.

## Output structure

Use the headings from `templates/decision-note.md` exactly, in this order:
`## Context`, `## Options considered`, `## Decision`, `## Rationale`, `## Consequences`, `## Links`.

Skip a section by omitting its body and the heading rather than rendering placeholder text like "TBD" or "N/A".

After writing, return a short JSON line with `{tok_in, tok_out, files_written, errors}` for the audit log.
