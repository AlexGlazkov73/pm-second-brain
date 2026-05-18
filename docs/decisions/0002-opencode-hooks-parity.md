# ADR 0002 — OpenCode hooks API parity with Claude Code

**Status:** Provisional — needs end-to-end verification on macOS
**Spike task:** Task 2 (Phase 0)

## Context

The self-evolution loop relies on `PostToolUse`, `SessionStart`, and `Stop` hooks
firing identically in **OpenCode** and **Claude Code**. Spec §13 asks whether a
thin bash adapter is needed to normalize payload shapes between the two runtimes.

## Decision

**Provisional:** Ship a thin bash adapter `hooks/adapter.sh` that normalizes
hook stdin payloads to a single canonical shape before invoking the real hook
scripts (`context-monitor.sh`, `workflow-guard.sh`, `prompt-guard.sh`,
`post-task-evolve.sh`, `session-start.sh`).

Rationale:

- Claude Code hooks (as of 2026-05) pass a structured JSON object on stdin with
  fields like `tool_name`, `tool_input`, `tool_response`, `session_id`,
  `cwd`, `transcript_path`.
- OpenCode hook surface is broadly similar but field names and nesting may
  differ (e.g. `event` vs `hook_event_name`; flat vs nested `tool`).
- An adapter is cheap (one bash script with `jq`), easy to test, and isolates
  every other hook from runtime-specific quirks.

## Canonical payload shape

```json
{
  "runtime":       "claude" | "opencode",
  "event":         "PostToolUse" | "SessionStart" | "Stop" | ...,
  "tool":          "<tool name>",
  "tool_input":    { ... },
  "tool_response": { ... },
  "session_id":    "<id>",
  "cwd":           "<absolute path>",
  "ts":            "<ISO-8601 UTC>"
}
```

## Verification status

This ADR is **provisional**. Phase 5 installation must:

- [ ] Verify `opencode` and `claude` CLI versions print on a real macOS box
- [ ] Capture one PostToolUse stdin sample from each runtime to
      `docs/decisions/0002-evidence/{opencode,claude}-stdin.json`
- [ ] Update this ADR with the actual field differences
- [ ] Decide whether the adapter can be **removed** if shapes already match,
      or whether it stays as a future-proofing layer

Until verified, every hook script must invoke `adapter.sh` first.
