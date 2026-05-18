---
name: pm-verify-output
description: Pre-write sanity check on any proposed file write. Cheap, fast.
allowed_tools: ["Read"]
model_preference: "claude-haiku-4-5"
inputs: { proposed_content: "string", target_path: "string", vault_root: "string — absolute path to vault root; defaults to CWD if absent" }
---

# pm-verify-output

## Overview

Single-phase, stateless, read-only check. The caller passes the full
`proposed_content` string (what is about to be written to disk) and the
`target_path` (vault-root-relative, e.g., `decisions/2026-05-17-foo.md`).
The skill returns a structured verdict; it does **not** write anything,
does **not** modify the vault, and does **not** emit audit events.
The caller is responsible for deciding what to do with the verdict.

If any check returns `severity: "block"`, the overall verdict is `ok: false`
and the caller MUST surface the issues to the user before writing.
`severity: "warn"` issues are advisory only and do not flip `ok` to false
on their own.

---

## Steps

### Step 1 — Detect note type

Detect the note type from `proposed_content` and `target_path`:

1. Parse the YAML frontmatter block at the top of `proposed_content`
   (between the first `---` line and the next `---` line). If a `type:`
   field exists, use its value (lowercased): one of `decision`, `meeting`,
   `daily`. Any other value → `unknown`.
2. If no `type:` field is present, infer from `target_path`:
   - prefix `decisions/` → `decision`
   - prefix `meetings/` → `meeting`
   - prefix `daily/` → `daily`
   - otherwise → `unknown`

Store the result as `note_type`. It is returned in the output JSON and
drives the required-fields check in Step 7.

### Step 2 — YAML frontmatter parses

- The file must begin with `---` on line 1.
- A second `---` line must close the block.
- Lines between must parse as YAML.

If any of these conditions fails:
- `{ check: "frontmatter", severity: "block", message: "<concrete reason>" }`

Concrete reasons (kebab-case sentence style):
- `frontmatter block missing — expected --- on line 1`
- `frontmatter block not closed — missing trailing ---`
- `frontmatter yaml does not parse: <parser error excerpt>`

### Step 3 — No transclusions

Scan `proposed_content` for the regex `!\[\[[^\]]+\]\]`.

Each match → one issue:
- `{ check: "transclusion", severity: "block", message: "transclusion not allowed: <full match>" }`

Report at most 3 distinct matches (deduplicate by full match text); if more
exist, append one extra issue:
- `{ check: "transclusion", severity: "block", message: "additional transclusions truncated: <N> more" }`

### Step 4 — Wikilink resolution

Extract all wikilinks using the regex `\[\[([^\]|]+)(?:\|[^\]]*)?\]\]`
(same pattern as `pm-link-notes`). The path portion is the capture group
(everything before `|`).

For each unique link target:

1. Strip an optional trailing `.md` and lowercase the comparison key.
2. Resolve wikilink targets against `<vault_root>` (taken from the
   `vault_root` input, or the current working directory if `vault_root`
   is absent). `target_path` is vault-root-relative; each wikilink
   resolves to `<vault_root>/<target>.md`. The verifier never derives
   vault root from `target_path` alone.
3. Check whether the file exists on disk.

Unresolved links → one issue each, with `warn` severity (never `block`):
- `{ check: "unresolved-link", severity: "warn", message: "wikilink target not found: <target>" }`

A wikilink that points to the same path as `target_path` (a self-link) is
also reported as `unresolved-link` with message
`wikilink target is self-link: <target>`.

Cap the unresolved-link issues at 10; if more exist, append one extra
warn issue: `additional unresolved links truncated: <N> more`.

### Step 5 — No raw secrets

Scan `proposed_content` for the regex patterns in `prompt.md` (Bearer
tokens, OpenAI `sk-` keys, Anthropic `sk-ant-` keys, GitHub `ghp_`
tokens, AWS `AKIA` access keys).

Any match → one `block` issue:
- `{ check: "secret", severity: "block", message: "possible <kind> secret detected" }`

Where `<kind>` is one of `bearer-token`, `openai-key`, `anthropic-key`,
`github-token`, `aws-access-key`. Do **not** include the matched text
itself in the message — leaking the secret into the output would defeat
the check.

Report at most one issue per kind even if multiple matches occur.

### Step 6 — Body length ≤ 1000 lines

Total line count is computed as `len(proposed_content.split("\n"))`.
This count includes the YAML frontmatter, all blank lines, and the
trailing newline (if any). A file ending with `\n` does NOT produce
an extra empty line in the count — Python's `split("\n")` behavior is
the reference.

- If the count exceeds 1000:
  `{ check: "length", severity: "block", message: "body exceeds 1000 lines (got <N>)" }`

### Step 7 — Required frontmatter fields per type

Apply per-type rules to the parsed frontmatter:

| `note_type` | Required fields |
|---|---|
| `decision` | `date`, `project` |
| `meeting`  | `date`, `project`, `participants` |
| `daily`    | `date` |
| `unknown`  | none beyond a parseable YAML block |

For each missing or empty field:
- `{ check: "required-fields", severity: "block", message: "missing required field for <note_type>: <field>" }`

A field is considered missing if:
- the key is absent from frontmatter, or
- the value is `null`, an empty string, or an empty list.

The `type:` field itself is **not** required; type detection falls back
to path-prefix inference.

### Step 8 — Compose verdict

Collect all issues from Steps 2-7. The verdict:

- `ok` = `true` if and only if no issue has `severity: "block"`.
- `issues` = the collected issues in the order they were generated.
- `note_type` = the value from Step 1.

Return the JSON shape defined in `prompt.md`. Stop.

---

## Input / output contract

**Inputs:**
- `proposed_content` (string, required): the full text that would be
  written to disk, including frontmatter.
- `target_path` (string, required): vault-root-relative path where the
  content would be written.
- `vault_root` (string, optional): absolute path to the vault root used
  to resolve wikilinks. If absent, the current working directory is
  used. The verifier never derives vault root from `target_path` alone.

**Output:** single JSON object (see `prompt.md` for the full shape and
example values).

**Side effects:** none. This skill does not write, does not modify the
vault, and does not emit audit events. The caller decides what to do
with `ok: false` (typically: surface issues, abort write, ask user to
fix).

---

## Safety

- Read-only. The skill never writes to disk and never modifies any file.
- No audit log entries are emitted by this skill. The caller may emit
  its own audit event referencing the verdict.
- Secret detection deliberately omits the matched text from the message
  to avoid leaking secrets into the verdict payload.
- Severity is restricted to exactly two values: `block` and `warn`. No
  other levels are produced.
