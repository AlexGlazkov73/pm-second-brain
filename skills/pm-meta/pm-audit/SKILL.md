---
name: pm-audit
description: Weekly pattern scan over _brain/audit/*.jsonl. Surface frequent corrections, expensive flows, regressions. Optionally trigger pm-evolve for top patterns.
allowed_tools: ["Read", "Write"]
model_preference: "claude-sonnet-4-6"
inputs:
  trigger_evolve: "false | true — default: false; when true, the audit may invoke /pm-meta.pm-evolve for top patterns"
  window_days: "int — default: 14; how many days of audit history to load"
---

# pm-audit

## Overview

Single-phase, stateless scan over the audit log. Loads the last N
days of `_brain/audit/<YYYY-MM>.jsonl`, aggregates events by type and
by originating skill, detects three classes of pattern (frequent
corrections, cost anomalies, regressions), and writes a Markdown
summary at `<brain_dir>/audit/weekly-<YYYY-WW>.md`. Optionally, when
`trigger_evolve: true`, invokes `/pm-meta.pm-evolve` for each
correction pattern that crosses threshold.

This is the reader half of the self-improvement loop. The writer half
is `pm-evolve`, which composes the actual patches. `pm-audit` makes
zero claims about which lines of which skill to change — it only
reports patterns and (optionally) hands targets to `pm-evolve`.

The skill writes exactly one Markdown report and emits exactly one
audit event (`weekly-audit-done`). It may also emit additional
`cost-anomaly` audit events, one per skill exceeding the anomaly
threshold. When `trigger_evolve: true`, each invocation of
`/pm-meta.pm-evolve` produces its own `patch-proposed` event owned
by that sub-call, not by this skill.

---

## Steps

### Step 1 — Load audit history

Compute the audit window:

- `<window_days>` = the input `window_days`, default 14. Must be a
  positive integer ≤ 90. Invalid input → audit `weekly-audit-done`
  with `errors: ["invalid-window-days: <value>"]` and stop.
- `<now>` = current UTC datetime.
- `<from>` = `<now>` − `<window_days>` days.

Enumerate `<brain_dir>/audit/<YYYY-MM>.jsonl` files whose month
overlaps `[<from>, <now>]`. For a 14-day window, this is at most two
files; for 90 days, at most four. Read each file line by line, parse
each JSON object, and keep events whose `ts` field falls in
`[<from>, <now>]`. Drop events outside the window.

Failure modes:

- `<brain_dir>/audit/` does not exist → treat as zero events; produce
  a report that says "no audit history in window" and emit
  `weekly-audit-done` with `event_count: 0`.
- A single line fails to parse → record one entry in `errors`
  (`audit-line-parse-failed: <file>:<line_no>`) and continue with the
  rest of the file.
- A whole file is unreadable → record `audit-file-unreadable: <file>:
  <reason>` and continue with the other files.

The loaded events stay in memory only; no normalized store is
written.

### Step 2 — Aggregate by event type and by skill

Build two indices over the loaded events:

- `events_by_type` — `dict[event_name, list[event]]`. Group by the
  `event` field (e.g., `correction`, `patch-proposed`, `self-review`,
  `moc-rebuilt`, `revert-on-error`, `tool-use`).
- `events_by_skill` — `dict[skill_name, list[event]]`. The skill name
  is inferred per event:
  - `correction` events: `target_skill` field, falling back to a
    `skill` field, then to `target` parsed as
    `skills/<ns>/<leaf>/...` → `<leaf>`.
  - `patch-proposed` events: parse `target` field for `<leaf>`.
  - `self-review` events: infer the originating skill from `path` via
    the same table `pm-self-review` uses (`decisions/` →
    `pm-decision`, `meetings/` → `pm-meeting-recap`, `daily/` →
    `pm-daily-brief`).
  - `moc-rebuilt`, `patch-applied`, and other skill-bound events:
    use the event's own `skill` field if present; otherwise the leaf
    name embedded in `target` / `path`.
  - Events with no resolvable skill go into `events_by_skill["_unknown"]`.

These indices feed Step 3 directly.

### Step 3 — Detect patterns

Three pattern classes are computed against the aggregated indices.
Each crossing of a threshold becomes one `Finding` in the report
(see Step 4) and, conditionally, one downstream action.

#### 3a — Frequent corrections per skill

For each `skill_name` in `events_by_skill`:

- Count `correction` events for that skill within the last 7 days
  (a sub-window inside the 14-day default load — corrections
  decay faster than long-term drift).
- If `count >= 3`: this skill is a candidate for `pm-evolve` with
  `trigger: PATTERN`. Record a `Finding`:
  - `kind: "frequent-corrections"`
  - `skill: <skill_name>`
  - `count: <int>`
  - `evidence: [<event_ts_or_path>, ...]` (up to 5 representative
    event IDs; the audit `ts` makes a good ID)
  - `suggested_target: skills/<ns>/<leaf>/SKILL.md` (resolved by
    looking up `<leaf>` in the on-disk `skills/` tree; falls back to
    `prompt.md` only if `SKILL.md` does not exist for that leaf)

The "3 within 7 days" threshold is the plan default; it can be
tightened by `evolution.pattern_threshold` in future iterations (the
current `Evolution` config exposes `pattern_threshold: float = 0.7`
which is a fractional threshold; the integer-count threshold of `3`
remains the v0 trigger because the fractional form requires a
denominator the v0 audit log does not yet provide).

#### 3b — Cost anomaly per skill

For each `skill_name` in `events_by_skill`:

- Pull all `tool-use` events for that skill in the 14-day window
  (`event: "tool-use"` is emitted by the host harness, not by
  individual skills, and carries `tok_in`, `tok_out`, `cost_usd`).
- Bucket events by UTC date.
- Compute per-skill daily cost = sum of `cost_usd` per bucket.
- Compute the median and 95th percentile across the available daily
  buckets.
- If `p95 > 2 * median` AND `p95 > 0.01` (the floor avoids false
  positives on near-zero costs): emit a Finding:
  - `kind: "cost-anomaly"`
  - `skill: <skill_name>`
  - `median_usd_per_day: <float, 4 decimals>`
  - `p95_usd_per_day: <float, 4 decimals>`

Each `cost-anomaly` Finding also produces a standalone
`cost-anomaly` audit event (verbatim per plan):

```json
{
  "event": "cost-anomaly",
  "skill": "<skill_name>",
  "median_usd_per_day": <float>,
  "p95_usd_per_day": <float>,
  "window_days": <int>
}
```

If `tool-use` events are not present in the audit log (e.g., the
harness has not yet started emitting them), `cost-anomaly` detection
silently skips and adds `cost-anomaly-data-unavailable` as a
non-fatal note in the report.

#### 3c — Regression flag (revert-on-error)

For each `revert-on-error` event in the last 7 days:

- Read `target_skill` (or `target` parsed for `<leaf>`).
- Emit a Finding:
  - `kind: "regression-flag"`
  - `skill: <skill_name>`
  - `ts: <event ts>`
  - `evidence: [<reverted_patch_ts>, ...]`

Regression flags are always surfaced — there is no count threshold.
A single `revert-on-error` event in the window is enough to
recommend user review.

Why a 7-day sub-window (instead of the full `window_days`)? Recent
regressions are more actionable than historical ones; the 7-day
sub-window matches the frequent-corrections threshold so a fresh
revert can be correlated with a fresh correction pattern on the
same skill.

### Step 4 — Write weekly report

Compute the ISO week label:

- `<YYYY>` = ISO year of `<now>` (UTC).
- `<WW>` = zero-padded ISO week number of `<now>`.
- Combined: `<YYYY>-W<WW>` (e.g., `2026-W20`).

Write to `<brain_dir>/audit/weekly-<YYYY>-W<WW>.md`. Use a Markdown
document with sections (no embedded JSON). Full layout in
`prompt.md`. If the file already exists for this week, overwrite it
— the weekly report is idempotent within an ISO week.

The report covers at minimum:

- header (window dates, event count, errors count),
- frequent-corrections section (one bullet per Finding),
- cost-anomaly section (one bullet per Finding),
- regression-flag section (one bullet per Finding),
- summary numbers (per-skill event counts).

If no findings of a given kind exist, render the section heading
followed by `(none)`.

### Step 5 — Conditional pm-evolve hand-off

When `trigger_evolve: true`:

- For each `frequent-corrections` Finding, invoke
  `/pm-meta.pm-evolve` with:
  - `target: <suggested_target>`
  - `trigger: PATTERN`
  - `pattern_evidence: [<event_ts_or_path>, ...]` (from the
    Finding's `evidence` list)
- `cost-anomaly` and `regression-flag` Findings do NOT trigger
  `pm-evolve` automatically; they require human judgment.

Each `pm-evolve` sub-call owns its own audit event. This skill does
not aggregate sub-call results into its own report (the report
captures only the patterns detected; the proposals appear in
subsequent `patch-proposed` audit events visible in the next weekly
scan).

If `trigger_evolve: false` (default), Step 5 is a no-op.

### Step 6 — Emit audit

Emit exactly one `weekly-audit-done` event regardless of how many
findings the report contains:

```json
{
  "event": "weekly-audit-done",
  "window_days": <int>,
  "event_count": <int>,
  "findings": {
    "frequent_corrections": <int>,
    "cost_anomaly": <int>,
    "regression_flag": <int>
  },
  "report_path": "<brain_dir-relative path>",
  "trigger_evolve": true | false,
  "evolve_invocations": <int>,
  "errors": []
}
```

`evolve_invocations` counts how many `/pm-meta.pm-evolve` sub-calls
were issued in Step 5 (always `0` when `trigger_evolve: false`).

Additionally, one `cost-anomaly` audit event is emitted per skill
exceeding the threshold (see Step 3b). Those events are independent
from the `weekly-audit-done` summary — they let downstream consumers
react to anomalies without re-parsing the weekly report.

---

## Input / output contract

**Inputs:**
- `trigger_evolve` (bool, optional, default `false`): when `true`,
  hand frequent-corrections Findings to `pm-evolve`.
- `window_days` (int, optional, default `14`): how many days of
  audit history to load. Must be in `[1, 90]`.

**Output:** single JSON object summarizing the scan (full shape in
`prompt.md`).

**Side effects:**
- One Markdown file written to
  `<brain_dir>/audit/weekly-<YYYY>-W<WW>.md` (overwrites within
  the same ISO week).
- One `weekly-audit-done` audit event per invocation.
- Zero or more `cost-anomaly` audit events (one per anomalous skill).
- Optional sub-calls to `/pm-meta.pm-evolve` when
  `trigger_evolve: true`; sub-calls emit their own audit events
  (`patch-proposed`), not owned by this skill.

---

## Safety

- Read-only over the audit log. The skill does not modify or
  truncate any `.jsonl` file.
- Write target is restricted to one Markdown file under
  `<brain_dir>/audit/`. The skill does not touch `skills/`,
  `decisions/`, `meetings/`, `daily/`, or `mocs/`.
- `cost-anomaly` thresholds carry a $0.01 floor to suppress
  false positives on near-zero spend.
- Regression flags surface unconditionally — even one
  `revert-on-error` in the window justifies user attention.
- The `trigger_evolve` knob is off by default. When on, it only
  produces proposals (via `pm-evolve`), never applied patches —
  `pm-evolve`'s own gates (self-patch refusal, daily rate limit,
  weekly cap, in-flight deferral) remain in force.
- Audit event names (`weekly-audit-done`, `cost-anomaly`) are
  verbatim per the plan. `pm-evolve`'s names (`patch-proposed`,
  `meta-self-patch-blocked`) appear only as references — this
  skill does not emit them.
