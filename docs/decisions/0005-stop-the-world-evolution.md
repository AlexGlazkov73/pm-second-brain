# ADR 0005 — Stop-the-world evolution policy

**Status:** Accepted (2026-05-17)
**Spike task:** Task 4 (Phase 0)

## Decision

**Defer:** if `pm-meta.pm-evolve` fires while its target skill is part of the
*active session*, the evolution step only writes a `proposed-patch-<ts>.md` —
it never patches the live SKILL.md mid-session.

A `SessionStart` hook on the **next** session scans
`_brain/skills/<ns>/<leaf>/proposed-patch-*.md` and surfaces a one-line summary
to the user, who can apply (`/pm-apply-patch <ts>`) or discard.

## Reasoning

- Patching a skill that the agent is currently using would cause unpredictable
  mid-session drift (think "swapping the steering wheel while driving").
- Deferring keeps the contract simple: the only place SKILL.md can change is
  between sessions, never inside one.
- The `proposed-patch-*.md` file is a self-describing artifact: it lives next
  to the target skill, has a timestamped filename, and contains both the
  rationale and a unified diff. The user can review it without re-running
  pm-evolve.

## Safety properties this enforces

| Property                                       | How                                                         |
|------------------------------------------------|-------------------------------------------------------------|
| Skill code never silently mutates              | Patches land in `proposed-patch-*.md`, not in `SKILL.md`.   |
| Snapshots before any apply                     | `history.snapshot()` always runs before `patch.apply()`.    |
| Auto-revert on regression                      | Smoke-test fails after apply → `history.revert_latest()`.   |
| `pm-meta` cannot patch `pm-meta`               | Hard-coded skip rule in `pm-evolve`, audit-logged.          |
| Trivial patches can auto-apply (config.yaml)   | Only typo / whitespace / formatting; classified by `patch.py`. |

## Out of scope for v0

- Per-skill override of "deferred vs trivial-auto-apply" — global flag for now.
- Cross-session patch queue across multiple vaults.
