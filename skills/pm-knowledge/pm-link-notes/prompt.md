You are linking a vault note to similar notes by discovering candidates via full-text search and proposing wikilinks.

Output **language**: {{lang}}.

---

## Stop-word list

Tokens matching any entry in these lists are dropped before search. Comparison is case-insensitive. Tokens shorter than 3 characters are also dropped. Purely numeric tokens (matching `^\d+$`) are also dropped.

**English stop words (26):**
`a, an, and, are, as, at, be, by, for, from, has, have, in, is, it, of, on, or, that, the, this, to, was, were, with, will`

**Russian stop words (26):**
`и, в, на, с, что, как, это, по, для, не, но, или, же, бы, был, была, если, есть, у, мы, я, ты, он, она, они, нет`

Apply both lists. The combined stop-word set is: the union of all words above. A token matching any entry in either list is dropped regardless of the document language.

---

## Token extraction order

If the target file has no YAML frontmatter block (no `---` delimiter pair at the start of the file), treat all frontmatter fields (`tags`, `title`, `date`, `project`) as absent and proceed with body-only token extraction.

Extract tokens from these three sources in sequence:

1. **Title** (H1 or frontmatter `title`):
   - Scan the body for the first line matching `^# .+`. Strip the leading `# ` prefix.
   - If no H1 found, use the `title` field from YAML frontmatter.
   - If neither found, skip this source entirely — token extraction proceeds from tags and first paragraph only.
   - Split on whitespace and punctuation: `[\s.,;:!?()\[\]{}"'«»—\-/\\]+`.

2. **Frontmatter `tags`**:
   - Read the `tags` field from YAML frontmatter.
   - If `tags` is a scalar string rather than a list, treat it as a single-element list before processing.
   - Each tag is a single token — do not split on hyphens or underscores.
   - Example: tag `product-strategy` → token `product-strategy` (kept as-is, then stop-word-checked as a whole).

3. **First non-empty paragraph after frontmatter**:
   - Skip: the YAML frontmatter block (`---` ... `---`), the H1 line, any blank lines after the H1.
   - Take the first run of consecutive non-empty, non-heading lines.
   - Split on whitespace and punctuation (same pattern as above).

Concatenation and deduplication:
- Concatenate tokens from sources 1, 2, 3 in order.
- Lowercase all tokens.
- Apply stop-word filtering (both lists).
- Drop tokens shorter than 3 characters.
- Drop purely numeric tokens.
- Deduplicate: if the same token appears more than once (case-insensitively), keep only the first occurrence.
- Cap at 8 tokens (take the first 8 after deduplication).

---

## 365-day freshness rule

For each candidate note discovered via `fts_search`:

1. Detect the candidate's date:
   - Try frontmatter `date` field (ISO `YYYY-MM-DD` string, e.g., `date: 2025-04-10`).
   - If absent, try the filename: extract a `YYYY-MM-DD-` prefix from the basename (e.g., `2025-04-10-some-topic.md` → `2025-04-10`).
   - If no date is detectable, treat the candidate as undated (do not apply the freshness rule).

2. Compute the candidate's age in days from today's date.

3. Apply the rule only if all of the following are true:
   - The candidate's age exceeds 365 days.
   - The candidate's `project` frontmatter field is non-empty.
   - The target note's `project` frontmatter field is non-empty.
   - The two `project` values differ (case-insensitive comparison).

4. If all conditions are true: drop the candidate.

5. If any condition is false (undated, either side lacks `project`, or projects match): keep the candidate.

The freshness rule is applied after BM25 ranking and before the minimum-3-candidates check in Step 7 of SKILL.md.

---

## BM25 ranking and aggregation

Each candidate's score is the raw sum of its per-token BM25 scores across all `fts_search` calls that returned it. There is no normalization by token-coverage count. Candidates matching more token queries tend to rank higher (intended). A candidate matching a single high-scoring query may still outrank multi-token matches — this is acceptable for v0.

---

## `## Related` section grammar

### Heading

- Section heading canonical form: `## Related` (level-2 Markdown heading, title-cased, no trailing whitespace).
- Detection is **case-insensitive**: regex `^##\s+[Rr]elated\s*$` (match on a line by itself, case-insensitive). Variants such as `## related` or `## RELATED` are recognized as an existing Related section.
- When an existing heading is found with non-canonical case (anything other than `## Related`), record `related-heading-case-mismatch: <original_case>` in `errors` as a non-fatal warning. The existing heading's case is preserved verbatim — do NOT rename it.
- When creating a new Related section (no existing heading found in any case), always use `## Related` (canonical case).

### Bullet format

```
- [[<path-without-md>]] — <Title>
```

- `<path-without-md>`: vault-root-relative path with the `.md` extension stripped. Example: `decisions/2026-05-17-foo` (not `decisions/2026-05-17-foo.md`).
- ` — `: em dash surrounded by single spaces (U+2014 `—`), not a double-hyphen `--`.
- `<Title>`: the candidate note's H1 heading, or the filename slug (basename without `.md`, hyphens replaced by spaces, title-cased) if no H1 is found.
- One bullet per line. No sub-bullets.

### Ordering

- New bullets are sorted by descending aggregated BM25 score (highest score first).
- When appending to an existing `## Related` section, new bullets are added at the end of the section, after all pre-existing bullets. Pre-existing bullets are never reordered.

### Preservation

- Never modify existing bullets in `## Related`.
- Never modify any other section, frontmatter field, or blank line outside the section write target.

---

## Wikilink resolution for existing-link filter

When checking whether a candidate path already exists in the target note as a wikilink, match against all of the following forms:

- `[[path/slug]]`
- `[[path/slug|any alias text]]`
- `[[path/slug.md]]`
- `[[path/slug.md|any alias text]]`

Matching is **case-insensitive** on the path portion only. The alias text (after `|`) is ignored for matching purposes.

Example: if a candidate path is `decisions/2026-05-17-foo`, it matches any of:
- `[[decisions/2026-05-17-foo]]`
- `[[decisions/2026-05-17-FOO|Foo decision]]`
- `[[decisions/2026-05-17-foo.md]]`

Normalization: strip `.md` suffix from both the candidate path and the extracted wikilink path before comparing.

---

## Confirmation token format

The `confirmation_token` is computed as:

```
confirmation_token = sha256( path + "\n" + "\n".join(sorted(candidate_paths)) )[:16]
```

- `path`: the vault-root-relative target path as provided in the invocation.
- `candidate_paths`: the list of surviving candidate paths (vault-root-relative, without `.md` extension), sorted lexicographically.
- The `\n` line-feed separator prevents collisions where concatenating two paths could produce the same string as different paths (e.g., `a/b` + `c` would equal `a/bc` without the separator).
- Truncate to the first 16 hexadecimal characters of the SHA-256 digest.

---

## Preview output format

When Phase 1 completes (no write to disk), output the following human-readable summary to the caller:

```
Linking: <target_path>
Action: <Append N new bullets to existing ## Related section | Add new ## Related section with N bullets>

Proposed links (sorted by relevance):
  1. [[<path1>]] — <Title1>  (score: <bm25_1>)
  2. [[<path2>]] — <Title2>  (score: <bm25_2>)
  ...

To apply, re-invoke with:
  approve: true
  confirmation_token: <16-char hex>
```

- Show at most 5 bullets.
- BM25 scores are rounded to 2 decimal places.
- Do not show raw `fts_search` JSON.
- Do not show the intermediate token list.
- If `errors` is non-empty, append after the bullets:
  ```
  Warnings: <error1>; <error2>
  ```

---

## Output JSON shape

After writing (Phase 2) or stopping (any step), return exactly one JSON object. There are four possible shapes:

**Phase 1 (preview, no write):**
```json
{
  "phase": 1,
  "tok_in": <int>,
  "tok_out": <int>,
  "files_written": [],
  "added_links": [],
  "confirmation_token": "<16-char hex>",
  "errors": []
}
```

**Phase 2 success (write completed):**
```json
{
  "phase": 2,
  "tok_in": <int>,
  "tok_out": <int>,
  "files_written": ["<target_path>"],
  "added_links": ["<path1>", "<path2>", ...],
  "errors": []
}
```
`added_links` contains vault-root-relative paths without `.md` extension, one entry per bullet written.

**Phase 2 mismatch (confirmation_token did not match recomputed token):**
```json
{
  "phase": 2,
  "tok_in": <int>,
  "tok_out": <int>,
  "files_written": [],
  "added_links": [],
  "errors": ["confirmation_token mismatch — re-run without approve:true to generate a fresh preview"]
}
```
Human-readable response: "Cannot apply: the candidate set has changed since the preview was generated. Re-run `pm-link-notes` without `approve:true` to see the updated preview."

**Stop-without-write — Phase 1 abort (e.g., insufficient tokens):**
```json
{
  "phase": 1,
  "tok_in": 120,
  "tok_out": 18,
  "files_written": [],
  "added_links": [],
  "errors": ["insufficient-tokens"]
}
```

**Stop-without-write — Phase 2 abort (e.g., token mismatch caught after re-discovery):**
```json
{
  "phase": 2,
  "tok_in": 240,
  "tok_out": 22,
  "files_written": [],
  "added_links": [],
  "errors": ["confirmation_token mismatch — re-run without approve:true to generate a fresh preview"]
}
```

Rules:
- Always emit the JSON object, even when stopping on error.
- An entry in `errors` does not suppress the JSON line.
- `files_written` contains only paths actually written during this invocation.
- `tok_in` and `tok_out` reflect the token counts for this invocation only.
- The `phase` field is always present (1 for preview or Phase 1 abort; 2 for write, write-failure, or Phase 2 abort).

**Error label reference (distinct keys):**

| Key | When emitted |
|-----|-------------|
| `insufficient-tokens` | Fewer than 3 tokens survive after all filtering (Step 2) |
| `not-enough-similar-notes` | Fewer than 3 candidates after BM25 ranking (Step 4) |
| `insufficient-candidates-post-linkfilter` | Fewer than 3 unique new candidates after existing-link filter (Step 5) |
| `insufficient-candidates-post-freshness` | Fewer than 3 candidates after 365-day freshness filter (Step 7a) |
| `confirmation_token mismatch — re-run without approve:true to generate a fresh preview` | Token provided in Phase 2 does not match recomputed token |
| `related-heading-case-mismatch: <original_case>` | Non-fatal: existing Related heading uses non-canonical case |
