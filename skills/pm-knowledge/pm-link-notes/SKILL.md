---
name: pm-link-notes
description: For one note path, find 3-5 most similar notes via fts_search and propose [[wikilink]] additions. Preview-first — never writes without explicit approve.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write", "fts_search"]
model_preference: primary
inputs: { path: "relative path inside vault (vault-root-relative)", approve: "false | true — default: false", confirmation_token: "token returned by Phase 1; required when approve is true" }
---

# pm-link-notes

## When to Use

When a freshly written or recently edited note should be cross-linked to similar existing notes in the vault. Invoked on-demand (user asks to "link related notes for X") or by a background cron job. Always runs in two stateless phases: Phase 1 builds a preview, Phase 2 writes after explicit approval with a matching confirmation token.

## Overview

Two-phase stateless skill.

- **Phase 1** (`approve: false`, default): discover candidates, build preview payload, return to caller without writing to disk.
- **Phase 2** (`approve: true`): caller re-invokes with the same `path` and the `confirmation_token` from Phase 1; skill re-runs discovery, validates the token, then writes.

The `confirmation_token` is a deterministic hash of `path + sorted(candidate_paths)`. Re-running discovery in Phase 2 and recomputing the token ensures the write always reflects fresh search state, and the token equality check prevents stale approval from being applied to a different candidate set.

Never write without going through Phase 1 first and receiving an explicit `approve: true` with a matching `confirmation_token`. If `confirmation_token` is absent or mismatched in Phase 2, emit `errors: ['confirmation_token mismatch — re-run without approve:true to generate a fresh preview']` and stop without writing.

## Quick Reference

| Field | Value |
|---|---|
| Phases | Phase 1 (preview, default) / Phase 2 (write, requires `approve: true` + token) |
| Token | `SHA256(path + "\n" + "\n".join(sorted(candidate_paths)))` truncated to 16 hex chars |
| Candidate count | Top 5 by aggregated BM25, filtered down to ≥3 unique new candidates |
| Token cap per `fts_search` invocation | 8 calls max |
| Freshness rule | Drop candidate if >365 days old AND target+candidate have differing non-empty `project` |
| Section target | `## Related` (case-preserving on append, canonical case on create) |
| Audit event | `notes-linked` (always emitted, with `target_path`, `added_links`, `errors`) |

## Procedure

### Step 1 — Validate input path

The target file path is vault-root-relative (e.g., `decisions/2026-05-17-foo.md`).

- If `path` is empty or whitespace: emit audit `notes-linked` with `errors: ['path is empty — provide a vault-root-relative path']`, `added_links: []`. Stop.
- Attempt to read the file at `<vault_root>/<path>`.
  - If the file is missing or unreadable: emit audit `notes-linked` with `errors: ['target file missing or unreadable: <path>']`, `added_links: []`. Stop.
- Store the raw file content for use in Steps 2 and 5.
- If the file has no YAML frontmatter block (no `---` delimiter pair at the start of the file), treat all frontmatter fields (`tags`, `title`, `date`, `project`) as absent and proceed with body-only token extraction in Step 2.

### Step 2 — Extract keyword tokens

Extract tokens from three sources in this order:

1. **Title**: look for a level-1 heading `# <Title>` in the body (first occurrence). If no H1 found, fall back to `title` in frontmatter. If neither is found, skip this source entirely — token extraction proceeds from tags and first paragraph only. Split the result on whitespace and punctuation (`[\s.,;:!?()\[\]{}"'«»—\-/\\]+`).
2. **Frontmatter tags**: read the `tags` field from YAML frontmatter. If `tags` is a scalar string rather than a list, treat it as a single-element list before processing. Each tag value is treated as a single token without splitting (e.g., `product-strategy` stays as one token).
3. **First non-empty paragraph**: the first paragraph of body text that follows the frontmatter block and any H1 line, where "paragraph" means one or more consecutive non-empty, non-heading lines (lines not starting with `#`). Split on whitespace and punctuation (same pattern as above).

Concatenate all candidate tokens. Lowercase all tokens. Apply stop-word filtering (list defined in `prompt.md`). Drop tokens shorter than 3 characters. Drop purely numeric tokens. Deduplicate case-insensitively (keep first occurrence). Cap at 8 tokens.

If fewer than 3 tokens remain after all filtering: record `insufficient-tokens` in `errors`, emit audit `notes-linked` with `added_links: []`, and stop without writing.

### Step 3 — Search similar notes

Call `fts_search(token)` once per token (maximum 8 calls total).

Collect all result paths from all calls. Deduplicate by path. Drop the target's own path from the result set.

On any single `fts_search` call failure: record `fts_search <error>` in `errors` and continue with the remaining tokens. If all calls fail: emit audit `notes-linked` with `added_links: []` and stop without writing.

### Step 4 — Rank by BM25

Each candidate path may appear in results from multiple token calls. Aggregate its BM25 score by summing the per-token BM25 values across all calls that returned it.

Sort candidates by aggregated BM25 score, descending. Keep the top 5.

**Aggregation note (known limitation):** Aggregation is a raw sum of per-token BM25 scores; no normalization by token-coverage count. Candidates matching more token queries tend to rank higher (intended). A candidate matching a single high-scoring query may still outrank multi-token matches — this is acceptable for v0.

If fewer than 3 candidates remain after ranking: record `not-enough-similar-notes` in `errors`, emit audit `notes-linked` with `added_links: []`, and stop without writing.

### Step 5 — Filter already-linked candidates

Parse the target note for all existing wikilinks using the pattern `\[\[([^\]|]+)(?:\|[^\]]*)?\]\]`. Extract the path portion (everything before `|` or `]]`).

Normalize each extracted path: strip `.md` suffix if present; lowercase. Normalize each candidate path the same way.

Drop from the top-5 candidate list any candidate whose normalized path matches any existing wikilink target. Matching is case-insensitive.

Also drop any candidate whose normalized path matches the target's own normalized path (guard against self-links).

If fewer than 3 unique new candidates remain after this filter: record `insufficient-candidates-post-linkfilter` in `errors`, emit audit `notes-linked` with `added_links: []`, and stop without writing.

### Step 6 — Resolve candidate titles

For each remaining new candidate:

1. Read the candidate file.
2. Extract its H1 heading. If H1 is absent, use the filename slug (the basename without `.md` extension, with hyphens replaced by spaces, title-cased).

Store each candidate as `{ path, title, bm25_score }`.

### Step 7 — Freshness filter, build preview, and conditional write

#### 7a — Apply 365-day freshness rule

For each candidate:

1. Detect the candidate's date: first try frontmatter `date` field (ISO `YYYY-MM-DD`). If absent, try a `YYYY-MM-DD-` prefix in the filename.
2. If the candidate's date is older than 365 days from today **and** both the target and the candidate have a non-empty `project` frontmatter field **and** those project values differ: drop the candidate.
3. If either the target or the candidate lacks a `project` field, do not apply the 365-day rule — keep the candidate.

If the count of surviving candidates falls below 3: record `insufficient-candidates-post-freshness` in `errors`, emit audit `notes-linked` with `added_links: []`, and stop.

#### 7b — Build preview (both phases)

Determine the preview action:

- Scan the target note for an existing Related section using a **case-insensitive** level-2 heading match: regex `^##\s+[Rr]elated\s*$` (match on a line by itself, case-insensitive).
  - If a matching heading is found: the action is **Append** — "Append <N> new bullets to existing `## Related` section".
  - Otherwise: the action is **Add** — "Add new `## Related` section with <N> bullets".
- If a Related heading is found with non-canonical case (e.g., `## related` or `## RELATED`), record `related-heading-case-mismatch: <original_case>` in `errors` as a non-fatal warning.

Sort the final candidates by descending BM25 score.

Each bullet in the preview uses the format:
```
- [[<candidate_path_without_md>]] — <candidate_title>  (<BM25 score>)
```

Compute the `confirmation_token` as:
```
SHA256(<path> + "\n" + "\n".join(sorted(<candidate_paths>)))
```
Truncate to 16 hex characters. The `\n` separator prevents collisions where concatenating two paths could produce the same string as different paths (e.g., path `a/b` + path `c` is distinct from path `a/bc`).

Return the Phase 1 payload without writing to disk:

```json
{
  "phase": 1,
  "action": "Append N bullets to existing ## Related" | "Add new ## Related section with N bullets",
  "preview": [
    { "bullet": "- [[path/slug]] — Title  (12.34)", "path": "path/slug", "bm25": 12.34 },
    ...
  ],
  "confirmation_token": "<16-char hex>",
  "tok_in": <int>,
  "tok_out": <int>,
  "errors": [...]
}
```

Do not show raw `fts_search` JSON in the preview. Present the preview as a human-readable summary to the user (see `prompt.md` for the exact format).

If `approve: false` (or absent): stop here and return the Phase 1 payload. Do not write to disk.

#### 7c — Write (Phase 2 only, when `approve: true`)

Triggered only when `approve: true` is present in the invocation.

Verify that `confirmation_token` (provided by the caller) matches the token recomputed from the current candidate set. If mismatch: record `confirmation_token mismatch — re-run without approve:true to generate a fresh preview` in `errors` and stop without writing. Return the error payload immediately to Step 8.

**If target has an existing `## Related` section** (detected via case-insensitive regex `^##\s+[Rr]elated\s*$`):

- Locate the section line. Keep the existing heading's case verbatim — do NOT rename `## related` to `## Related`.
- The section body extends from the line after the heading through the line before the next `##` heading (or end of file).
- Append new bullets at the end of the section body (after all existing content of that section), preserving existing bullets verbatim and in their original order.
- New bullets are sorted by descending BM25 (highest first).
- Write exactly the modified file back. Do not touch frontmatter, other sections, or blank lines outside the `## Related` section.

**If target has no `## Related` section:**

- Append to the file: one blank line separator (if the file does not end with a blank line, add one; if it already ends with one blank line, add none; never produce two or more trailing blank lines before the new section), then `## Related` (canonical case — always use this when creating a new section), then a blank line, then the bullets.
- Bullets are sorted by descending BM25 (highest first).

**Bullet format on disk** (no BM25 annotation — annotation is preview-only):
```
- [[<candidate_path_without_md>]] — <candidate_title>
```

Never modify frontmatter, body sections other than `## Related`, or existing bullets in `## Related`.

### Step 8 — Emit audit

Emit audit event `notes-linked` with:
```json
{
  "target_path": "<path>",
  "added_links": ["<path1>", "<path2>", ...],
  "errors": [...]
}
```

- On success (Phase 2 write completed): `added_links` contains the paths of all newly written bullets (without `.md`). `errors` contains any non-fatal issues.
- On Phase 1 (preview-only): `added_links: []`. `errors` contains any non-fatal issues.
- On stop-without-write at any step: `added_links: []`. `errors` contains the reason(s).
- Always emit this event, even on errors.

## Pitfalls

- Never write without going through Phase 1 first and receiving an explicit `approve: true` with a matching `confirmation_token`.
- If `confirmation_token` is absent or mismatched in Phase 2, do not write — emit the mismatch error and stop.
- Never modify frontmatter or body sections other than `## Related`.
- Never rename `## related` / `## RELATED` to canonical case on append; preserve the original case verbatim.
- Never produce two or more trailing blank lines before a newly created `## Related` section.
- Always emit the `notes-linked` audit event, even on errors and even when stopping without a write.
- Do not include BM25 scores in on-disk bullets — annotation is preview-only.

## Verification

- Phase 1: audit event `notes-linked` was emitted with `added_links: []`; the preview payload contains a `confirmation_token`, the chosen `action`, and ≥3 bullets sorted by descending BM25.
- Phase 2 success: the target file's `## Related` section contains the new bullets in descending BM25 order; frontmatter and all other sections are byte-identical to before; audit event `notes-linked` was emitted with non-empty `added_links`.
- Phase 2 mismatch: no write occurred; audit event `notes-linked` was emitted with `errors` containing `confirmation_token mismatch — re-run without approve:true to generate a fresh preview`.
- Any error path (missing target, insufficient tokens/candidates, all `fts_search` calls failed) emitted `notes-linked` with `added_links: []` and a descriptive error.
