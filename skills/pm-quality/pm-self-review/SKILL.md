---
name: pm-self-review
description: Post-write self-critique. Runs async, never blocks the user. Logs findings to audit.
allowed_tools: ["Read"]
model_preference: "claude-haiku-4-5"
inputs: { written_path: "string" }
---

# pm-self-review

## Overview

Single-phase, stateless, read-only critique that runs **after** a write
has already completed. The skill re-reads the file at `written_path`,
scores it on three dimensions (1-5 each), appends one JSON line to the
audit log, and returns the same payload to the caller. It is intended
to run asynchronously and never blocks the user.

**Non-modification guarantee:** this skill never writes to or modifies
`written_path` or any other vault file. Its only side effect is one
append to the audit log (`_brain/audit/<YYYY-MM>.jsonl`).

---

## Steps

### Step 1 — Read the written file

`written_path` is vault-root-relative (e.g.,
`decisions/2026-05-17-foo.md`).

- If `written_path` is empty or whitespace: append an audit line with
  `scores: null` and `notes: ["written-path-empty"]` and stop.
- Read the file at `<vault_root>/<written_path>`. If unreadable:
  append an audit line with `scores: null` and
  `notes: ["target file missing or unreadable: <written_path>"]` and
  stop.

### Step 2 — Detect note type and originating skill

Detect `note_type` the same way `pm-verify-output` does (frontmatter
`type:` field first; path-prefix inference as fallback).

Map `note_type` → `originating_skill` and fixture path:

| `note_type` | `originating_skill` | Fixture filename (under `<skills_root>/pm-workflow/<originating-skill>/fixtures/`) |
|---|---|---|
| `decision` | `pm-decision` | `sample-output.md` |
| `meeting`  | `pm-meeting-recap` | `sample-output.md` |
| `daily`    | `pm-daily-brief` | `sample-output.md` |
| `unknown`  | (none) | (none) |

Fixture lookup: `<skills_root>/pm-workflow/<originating-skill>/fixtures/sample-output.md`,
where `<skills_root>` is the directory containing the namespace folders
(`pm-workflow`, `pm-knowledge`, `pm-quality`, `pm-meta`). The host
harness provides this path — use the running skill's own SKILL.md path
and walk up two directory levels (from
`<skills_root>/<namespace>/<leaf>/SKILL.md` → `<skills_root>`).

If the fixture file cannot be read for any reason (does not exist,
e.g. `pm-meeting-recap` is a v0 skeleton; `note_type` is `unknown`; or
the file is otherwise unreadable): the tone-match score degrades to
neutral `3` and the note `tone-fixture-unavailable` is added.

### Step 3 — Score structural completeness (1-5)

Check the file's structure against the per-type expectations:

- `decision` notes: frontmatter present with `date` and `project`;
  body contains some prose (non-empty after frontmatter).
- `meeting` notes: frontmatter present with `date`, `project`,
  `participants`; body non-empty.
- `daily` notes: frontmatter present with `date`; body non-empty.
- `unknown`: frontmatter parses and body non-empty.

Scoring rubric is in `prompt.md`. Range: integer 1-5.

### Step 4 — Score citation density (1-5)

Count wikilinks using the regex `\[\[([^\]|]+)(?:\|[^\]]*)?\]\]`.
Count body lines (excluding frontmatter, blank lines, and YAML
delimiters). Compute density = (wikilink count) / (body line count) ×
100, i.e., wikilinks per 100 lines.

Bucketize per `prompt.md` rubric to a 1-5 score.

### Step 5 — Score tone match against fixture (1-5)

If the fixture from Step 2 is unavailable, score `3` and add
`tone-fixture-unavailable` to notes.

Otherwise, read the fixture and compare against the written file on:
- section headings and ordering,
- presence and shape of the same recurring elements (bullets,
  callouts, tables),
- prose register (compact vs verbose; declarative vs hedged).

Bucketize per `prompt.md` rubric to a 1-5 score.

### Step 6 — Compose notes

`notes` is a list of short kebab-case sentences flagging specific
findings. Examples:
- `low-citation-density: <N> links per 100 lines`
- `missing-section-for-meeting: agenda`
- `tone-drift-vs-fixture: prose more verbose than reference`
- `tone-fixture-unavailable`

Keep `notes` short. Do not include the full file content. Do not
include scores in the notes — those are already in `scores`.

### Step 7 — Append audit line and return

Append exactly one JSON line to `<brain_dir>/audit/<YYYY-MM>.jsonl`
where `<YYYY-MM>` is the current month in the vault's timezone and
`<brain_dir>` resolves to `_brain` under the vault root (see
`config.py` Folders default).

Audit event shape:

```json
{
  "event": "self-review",
  "path": "<written_path>",
  "scores": {
    "structural_completeness": <int 1-5>,
    "citation_density": <int 1-5>,
    "tone_match": <int 1-5>
  },
  "notes": ["..."]
}
```

The `ts` field is added by `audit_append` and must NOT be included in
the event payload emitted by this skill.

Note: `pm-link-notes` documents its audit payload with the `event:`
key external to the JSON example; this skill documents it inline.
Both forms write the same JSONL line via `audit_append`.

The audit append uses `audit_append(brain_dir, event)` semantics: one
JSON object per line, newline-terminated.

Return the same payload (without the `event` field) to the caller as
the skill's output JSON, per `prompt.md`.

---

## Input / output contract

**Inputs:**
- `written_path` (string, required): vault-root-relative path of the
  file that was just written.

**Output:** single JSON object (see `prompt.md` for shape and example).

**Side effects:**
- One append to `_brain/audit/<YYYY-MM>.jsonl` with
  `event: "self-review"`.
- No other writes. The reviewed file is never modified.

---

## Safety

- Read-only with respect to vault content. The reviewed file is never
  modified.
- The audit append is the only write; if the audit file does not
  exist, it is created. If the audit append itself fails, return the
  scoring payload to the caller and do not retry (the caller may
  handle the failure).
- Scores are integers in the closed range `[1, 5]`. Half-integers,
  zero, and out-of-range values are not produced.
- Audit event name is exactly `self-review` (matches the project's
  kebab-case audit-event naming).
