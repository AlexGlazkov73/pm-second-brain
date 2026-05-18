---
name: pm-meta
description: Meta-operations on the skill pack itself — self-review, audit-log queries, and (v1) the pm-progress smart router.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write"]
model_preference: primary
---

# pm-meta

## When to Use

When the user invokes a meta-operation on the skill pack (propose a patch, audit recent runs) or when a hook fires after a session. Triggered both manually (`/pm-evolve`, `/pm-audit`) and automatically (PostToolUse hook ≥ 5 calls, weekly cron).

## Quick Reference

| Trigger | Leaf |
|---|---|
| PostToolUse hook after ≥ 5 tool calls | `pm-evolve` (POST-TASK trigger) |
| User runs `/pm-evolve <skill>` | `pm-evolve` (MANUAL) |
| Weekly cron | `pm-audit` (PATTERN scan) |

`pm-progress` — placeholder, coming in v1. Trigger criteria: see `specs/2026-05-17-personal-second-brain-design.md` §14 FR-2.

## Procedure

1. Match the trigger to a leaf via the Quick Reference table.
2. Load only the matched leaf SKILL.md.
3. Delegate execution; aggregate audit events written by the leaf.

## Pitfalls

- `pm-meta.*` MUST NOT patch `pm-meta.*`. Skip with audit-event `meta-self-patch-blocked` ("petting the meta-pet").
- All patches land in `_brain/skills/<ns>/<leaf>/proposed-patch-<ts>.md`. Apply only via `/pm-apply-patch <ts>` or auto-apply when classified `trivial`.
- Snapshot every target before apply; on smoke-test regression, auto-revert.

## Verification

- The selected leaf wrote either a `proposed-patch-*.md` (pm-evolve) or an audit summary (pm-audit).
- No write went directly into a tracked SKILL.md without going through the patch lifecycle.
