---
adr: 0007
title: SKILL.md follows agentskills.io v1 + project-specific extensions
status: accepted
date: 2026-05-18
deciders: glazkov222@gmail.com
supersedes: []
---

## Context

The project ships 11 SKILL.md files (4 namespace + 7 leaf) with an ad-hoc frontmatter and inconsistent body layout. Phase 3 will add another 8 leaf skills. Two pressures push us toward a standardized format now:

1. **Portability.** A documented format is a prerequisite for any future skill sharing (research §4.7).
2. **Self-evolution.** `patch.py` (Phase 4, Task 27 — see this plan, Task 9) needs a stable section anchor (`## Procedure`, `## Verification`) to apply server-side validation on `auto_apply: trivial` patches. Without a canonical body order, regex-free validation is impossible.

## Decision

Adopt [agentskills.io](https://agentskills.io) **v1** as the canonical SKILL.md format, with two project-specific extensions.

### Required frontmatter (agentskills.io v1)

- `name` — kebab-case identifier matching the directory.
- `description` — third-person trigger description.
- `version` — semver, starts at `0.1.0`.
- `author` — handle of the maintainer.
- `license` — SPDX identifier, default `MIT`.

### Project-specific extensions (kept)

- `allowed_tools` — JSON array of tool names.
- `model_preference` — `primary` or `fallback`; resolved against the active `llm.profile`.

### Required body order

1. `## When to Use`
2. `## Quick Reference`
3. `## Procedure`
4. `## Pitfalls`
5. `## Verification`

### Deliberately omitted in v0

`platforms`, `required_credential_files`, `requires_toolsets`, `fallback_for_toolsets`. They will be added per leaf when a concrete need appears.

## Consequences

- All 11 existing SKILL.md must be refactored (see Tasks 3-4 of `tasks/plans/2026-05-18-second-brain-research-integration.md`).
- A pytest validator (`tests/skills/test_skill_frontmatter.py`) enforces the contract on every commit-equivalent run.
- `patch.py` can rely on the body section names being present and unique per file.

## Alternatives considered

- **Status quo (no format).** Rejected: blocks Phase 4 Task 27.
- **Hermes Agent full format.** Rejected for v0: optional fields add cognitive load with no current use-case.
