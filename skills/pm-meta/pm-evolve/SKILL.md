---
name: pm-evolve
description: Propose a patch to a target SKILL.md / prompt.md / MEMORY.md / USER.md based on session evidence. Writes to proposed-patch-<ts>.md; never modifies the target directly.
allowed_tools: ["Read", "Write", "fts_search"]
model_preference: "claude-sonnet-4-6"
inputs:
  target: "skills/<ns>/<leaf>/SKILL.md (or prompt.md, MEMORY.md, USER.md) — vault-root-relative"
  trigger: "POST-TASK | CORRECTION | PATTERN | MANUAL"
  correction_text: "string — required only when trigger=CORRECTION; the user's verbatim correction message"
  pattern_evidence: "list[string] — required only when trigger=PATTERN; session IDs that produced the pattern"
---

# pm-evolve

## Overview

Single-phase, stateless skill. Read evidence about how `target` has been
used and abused, compose a unified-diff patch with rationale, classify
the patch as `trivial` or `non-trivial`, and write the proposal to a
side file under `<brain_dir>/proposed-patches/<ns>/<leaf>/<ts>.md`. The
live `target` file is never modified by this skill itself; modification
happens only via `/pm-apply-patch` (manual) or, for trivial patches
under the safety gate, by calling `pm-apply-patch` immediately after the
proposal is written.

This is the writer half of the self-improvement loop. The reader half
is `pm-audit`, which detects patterns and may invoke `pm-evolve` with
`trigger: PATTERN`. The manual `/pm-evolve` command invokes it with
`trigger: MANUAL`. The PostToolUse hook invokes it with
`trigger: POST-TASK` after enough tool calls accumulate. Reviewer
corrections in chat invoke it with `trigger: CORRECTION`.

---

## Hard constraints

These run before any other step and abort the skill if violated.

1. **Self-patch is forbidden.** If `target` resolves to a path under
   `skills/pm-meta/` (any leaf in this namespace, including
   `pm-evolve` and `pm-audit` themselves and the namespace router
   `skills/pm-meta/SKILL.md`), refuse. Emit audit
   `meta-self-patch-blocked` with `{ target, trigger }` and stop
   without reading evidence, without composing a diff, and without
   writing a proposal. This rule is hard-coded and not overridable by
   config.
2. **Session-in-flight deferral (ADR-0005).** If a caller-supplied
   lockfile exists for `target` (operational definition below), the
   proposal is still written, but its frontmatter sets
   `apply_after_session_end: true`. The auto-apply branch in Step 7
   short-circuits: trivial patches are NOT auto-applied while their
   target is in-flight. The next session's `SessionStart` hook will
   surface the proposal to the user.
3. **One proposal per day per target.** If a `proposed-patch-*.md`
   for the same `target` already exists with a `<ts>` whose date
   component equals today (UTC), refuse this invocation. Emit audit
   `patch-proposed` with `{ target, ts: null, trivial: null, evidence:
   [], errors: ["daily-proposal-rate-limit: existing proposal at
   <existing_ts>"] }` and stop. Daily here means the UTC calendar day
   (00:00:00Z – 23:59:59Z).
4. **Weekly applied-patch cap.** Count proposals on `target` whose
   `<ts>` falls in the last 7 days (UTC) and whose `apply_status:
   applied` is recorded in the audit log (via `patch-applied` events
   emitted by `pm-apply-patch`; this skill does not emit them).
   - If `applied_count >= evolution.max_patches_per_week`: write the
     proposal as `non-trivial` regardless of diff classification, and
     set `force_user_review: true` in its frontmatter. This forces
     human approval even when the diff itself looks trivial.
5. **Trigger payload completeness.**
   - `trigger: CORRECTION` requires non-empty `correction_text`.
   - `trigger: PATTERN` requires non-empty `pattern_evidence`.
   - `trigger: POST-TASK` and `trigger: MANUAL` have no extra payload
     requirement.
   - Missing required payload → audit `patch-proposed` with
     `errors: ["trigger-payload-incomplete: <trigger> requires
     <field>"]` and stop without writing.

### Session-in-flight operational definition

A target is "in-flight" if and only if the lockfile
`<brain_dir>/locks/<sha256(target)[:16]>.lock` exists at the moment
`pm-evolve` runs.

- The lockfile is owned by the calling hook or harness. A
  `SessionStart`-style hook touches it when work on `target` begins;
  the matching session-teardown hook removes it. `pm-evolve` only
  checks for the file's presence — it never creates, writes, or
  deletes the lockfile.
- If `<brain_dir>/locks/` does not exist, treat the lock as ABSENT
  (no in-flight session). Do not invent a default-deferred mode and
  do not create the directory.
- If the lockfile path exists but is unreadable (permission error,
  I/O error), conservatively treat the target as IN-FLIGHT (defer
  the apply) and record `lockfile-unreadable: <reason>` in the
  proposal's `notes` field. This favors safety over throughput.

---

## Steps

### Step 1 — Resolve target and run hard constraints

`target` is vault-root-relative. The on-disk skill source layout is
`<vault_root>/skills/<ns>/<leaf>/<file>`. The plan's older reference
to `_brain/skills/<ns>/<leaf>/...` describes the *installed runtime*
mirror under `<brain_dir>`; this skill reads from and refers to the
source layout `skills/<ns>/<leaf>/` for diff anchoring, and writes
proposals to the brain-side proposed-patches tree (see Step 6).

- Normalize `target` by stripping a leading `_brain/` prefix (legacy
  callers) so the rest of the skill works on the source-layout form.
- Validate that `target` ends with one of: `SKILL.md`, `prompt.md`,
  `MEMORY.md`, `USER.md`. Any other suffix → audit `patch-proposed`
  with `errors: ["invalid-target-suffix: <target>"]` and stop.
- Apply the hard constraints in the order listed above
  (self-patch → in-flight → daily rate → weekly cap → payload).
- Read `target` from disk. If unreadable: emit
  `patch-proposed` with `errors: ["target-unreadable: <reason>"]` and
  stop.

### Step 2 — Gather evidence

Pull 3-10 recent session records from the FTS-indexed
`sessions.db`, filtered by the leaf name inside `target` (e.g., for
`skills/pm-knowledge/pm-rebuild-moc/SKILL.md`, search for
`pm-rebuild-moc`). Use `fts_search` with a small `limit` (≤ 10) and
record each hit's `path` and `title` for the `evidence` list.

Trigger-specific augmentation:

- `CORRECTION`: prepend the verbatim `correction_text` as
  `evidence[0]`, tagged with `source: "user-correction"`. The
  correction is the load-bearing signal; FTS hits are supporting
  context only.
- `PATTERN`: use the supplied `pattern_evidence` session IDs as the
  primary evidence, FTS as supplementary.
- `POST-TASK` and `MANUAL`: FTS hits are the only evidence source.

If `fts_search` returns zero hits AND there is no
`correction_text`/`pattern_evidence`: emit `patch-proposed` with
`errors: ["no-evidence: nothing to base a patch on"]` and stop.
Evidence-less patches are not allowed.

Cap the final `evidence` list at 10 entries. If more exist, keep the
10 highest-ranked.

### Step 3 — Compose the unified diff and rationale

Read the current `target` content. Propose a minimal edit that
addresses the evidence collected in Step 2. Emit a standard unified
diff with:

- 3 lines of context (`n=3`),
- `--- <target> (current)` and `+++ <target> (proposed)` file headers,
- `@@ ... @@` hunk markers.

Diff format details and rationale conventions are specified in
`prompt.md`. The diff must be applicable to the current `target` byte
content with no fuzz; if the proposed edit cannot be expressed as a
unified diff over the current file (e.g., total rewrite of a file
shorter than 5 lines), still emit a diff that replaces the whole file
— the `trivial` classifier in Step 4 will reject full-file rewrites
as non-trivial.

Rationale is a short paragraph (≤ 5 sentences) stating: what the
change does, which evidence motivates it, and what user-visible
behavior is expected to change.

### Step 4 — Classify trivial vs non-trivial

Classifier ordering — apply the structural-heading escalation
(see "added or removed section heading" below) BEFORE the
comment-only rule. The regex `^\s*(#|<!--|//).*$` would otherwise
swallow Markdown heading edits and misclassify them as trivial.
Once the heading check has run, a patch is `trivial` if and only
if every remaining hunk line in the diff matches at least one of
these patterns:

- whitespace-only change (regex over the line content after the
  leading `+`/`-`: `^\s*$` matches both removed and added forms),
- comment-only change (line content matches `^\s*(#|<!--|//).*$` on
  both sides, and the line was NOT already escalated as a heading
  edit),
- fixture-block-only change (the hunk is contained entirely within a
  fenced code block whose info string is `fixture`, `example`,
  `sample`, or `output` — detect by walking the surrounding context
  lines for the nearest preceding triple-backtick fence).

Any hunk line that does not match one of these three categories
flips classification to `non-trivial`. Examples that are explicitly
non-trivial: any change to an `allowed_tools` list, any change to
a `model_preference` value, any change to any other YAML
frontmatter key (anything between the leading `---` and the
closing `---` on a Markdown file), any change to step numbering or
step ordering, any change to audit event names, any added or
removed section heading.

Additional escalation rules:

- A diff that touches more than 40 lines total (added + removed) is
  forced to `non-trivial` regardless of content.
- If the weekly cap is hit (hard constraint #4), classification is
  forced to `non-trivial` and `force_user_review: true` is set.

Store the result as `trivial: true | false`.

### Step 5 — Choose proposal path and timestamp

Compute:

- `<ts>` = `YYYYMMDDTHHMMSSZ` (ISO-8601 basic, UTC, explicit `Z`
  suffix) computed from `datetime.now(timezone.utc)`. This format
  is intentionally distinct from `history.snapshot`'s local-time
  `YYYYMMDD-HHMMSS` so the two can never be confused at a glance.
- `<ns>` = the namespace directory under `skills/` (e.g.,
  `pm-knowledge`, `pm-workflow`, `pm-quality`).
- `<leaf>` = the leaf-skill directory under `<ns>` (e.g.,
  `pm-rebuild-moc`).
- Proposal path:
  `<brain_dir>/proposed-patches/<ns>/<leaf>/<ts>.md`.

`<brain_dir>` is the `_brain` folder under the vault root (see
`config.Folders.brain`, default `_brain`). The proposed-patches tree
is created lazily — `mkdir -p` the parent on first use.

This path location intentionally diverges from the older spec text
that placed proposals next to source SKILL.md. Rationale: keeping
proposals under `<brain_dir>/proposed-patches/` means

- the skill source tree stays free of timestamped clutter,
- `git`/installer flows that ship `skills/` don't sweep proposal
  files,
- the `SessionStart` hook has a single tree to walk
  (`<brain_dir>/proposed-patches/**/*.md`).

Special targets (`MEMORY.md`, `USER.md`) that do not live under
`skills/<ns>/<leaf>/` fall back to `<brain_dir>/proposed-patches/_root/<basename>/<ts>.md`.
The `_root` segment is reserved and never collides with a real
namespace: every real namespace segment must match
`^[a-z][a-z0-9-]*$`, so anything beginning with `_` (or otherwise
failing that regex) cannot be a valid namespace. If a derived
`<ns>` or `<leaf>` segment fails this regex, refuse the proposal
— see Safety for the audit shape.

### Step 6 — Write the proposal file

The proposal file is itself a Markdown document with a YAML
frontmatter block carrying machine fields, followed by human-readable
sections (rationale, diff, evidence). Full layout in `prompt.md`.

The skill's only write target is this one file. The skill MUST NOT:

- modify `target` directly,
- modify any other file in `skills/`,
- modify any MOC,
- modify any atomic note in `decisions/`, `meetings/`, `daily/`.

### Step 7 — Optional auto-apply (trivial only)

Auto-apply runs if and only if ALL of the following hold:

- `trivial == true`,
- `evolution.auto_apply_trivial == true` (config field, default
  `true`),
- `apply_after_session_end == false` in the just-written proposal
  frontmatter (hard constraint #2 already wrote `true` when the
  lockfile was present, so this flag is the single source of truth
  for in-flight state — do not re-check the lockfile here),
- weekly cap was NOT hit (no `force_user_review`),
- the daily rate limit did not abort earlier (we are past Step 1).

When the conditions hold, the skill calls `/pm-apply-patch <ts>`
with the proposal `<ts>` as the argument. `pm-apply-patch` is
responsible for the snapshot-before-apply and the smoke-test revert
path (see ADR-0005). This skill does not emit `patch-applied`; that
event is owned by `pm-apply-patch`.

When auto-apply is skipped (any condition false), the proposal
remains on disk awaiting `/pm-apply-patch <ts>` from the user or a
future hook.

### Step 8 — Emit audit

Emit exactly one `patch-proposed` event:

```json
{
  "event": "patch-proposed",
  "target": "<target>",
  "ts": "<YYYYMMDDTHHMMSSZ>",
  "trigger": "POST-TASK | CORRECTION | PATTERN | MANUAL",
  "trivial": true | false,
  "auto_applied": true | false,
  "apply_after_session_end": true | false,
  "force_user_review": true | false,
  "evidence": ["<event_ts_or_path>", "..."],
  "proposal_path": "<brain_dir-relative path>",
  "errors": []
}
```

The `ts` is added by `audit_append` and stored separately; the
`ts` field above is the *proposal* timestamp (filename component),
not the audit row timestamp. Both coexist.

For the `meta-self-patch-blocked` event (hard constraint #1):

```json
{
  "event": "meta-self-patch-blocked",
  "target": "<target>",
  "trigger": "POST-TASK | CORRECTION | PATTERN | MANUAL"
}
```

These two are the only audit events this skill emits. `patch-applied`
is emitted by `pm-apply-patch`. `meta-self-patch-blocked` is named
verbatim per the plan and the namespace router.

---

## Input / output contract

**Inputs:**
- `target` (string, required): vault-root-relative path to the
  Markdown file to patch.
- `trigger` (string, required): one of `POST-TASK`, `CORRECTION`,
  `PATTERN`, `MANUAL`.
- `correction_text` (string, required when `trigger: CORRECTION`):
  verbatim user correction.
- `pattern_evidence` (list of strings, required when
  `trigger: PATTERN`): session IDs feeding the pattern.

**Output:** single JSON object describing the proposal outcome (full
shape in `prompt.md`).

**Side effects:**
- One Markdown file written under
  `<brain_dir>/proposed-patches/<ns>/<leaf>/<ts>.md` (or the `_root`
  fallback for `MEMORY.md` / `USER.md`).
- One audit append per invocation (`patch-proposed` or
  `meta-self-patch-blocked`).
- Optional: one call to `/pm-apply-patch <ts>` when the auto-apply
  branch fires. That sub-call's own writes and audit are owned by
  `pm-apply-patch`, not by this skill.

---

## Safety

- The live `target` file is never modified by this skill. ADR-0005
  is the controlling reference for the stop-the-world property.
- `pm-meta.*` cannot patch itself. The self-patch guard is in
  Step 1's hard constraints and emits `meta-self-patch-blocked`
  verbatim.
- Session-in-flight detection is conservative: when in doubt
  (audit log unreadable, ambiguous session state), defer.
- Daily rate limit prevents proposal spam from runaway triggers.
- Weekly applied cap prevents drift accumulation; once
  `max_patches_per_week` is reached, every further patch needs
  explicit human review regardless of how trivial it looks.
- Auto-apply only ever runs on `trivial` patches that pass every
  gate; the snapshot-and-smoke-revert dance lives in
  `pm-apply-patch`, not here.
- Evidence-less patches are refused. Every proposal cites at least
  one session record or one user correction.
- Reserved namespace collision is refused. Any derived `<ns>` or
  `<leaf>` segment that fails `^[a-z][a-z0-9-]*$` (including
  anything starting with `_`) triggers a `patch-proposed` audit
  event with `errors: ["reserved-namespace-collision: <segment>"]`
  and `written: false`, and stops without writing the proposal.
