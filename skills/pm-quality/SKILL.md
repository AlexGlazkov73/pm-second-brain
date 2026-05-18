---
name: pm-quality
description: Quality-gate skills that check vault hygiene, broken links, frontmatter consistency, and skill-pack invariants.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read"]
model_preference: primary
---

# pm-quality

## When to Use

Before a vault-write proposal lands on disk, the namespace skill runs validation; after a write, it triggers self-review. Used both pre- and post-write to keep vault integrity intact.

## Quick Reference

| Trigger | Leaf |
|---|---|
| Any write-action proposed | `pm-verify-output` (pre-write) |
| User accepted a write | `pm-self-review` (post-write, async) |

## Procedure

1. Inspect the proposed write or completed write and select the matching leaf from the Quick Reference table.
2. Load only the matched leaf SKILL.md.
3. Delegate execution.

## Pitfalls

- Do not block legitimate writes on cosmetic issues — leaves report severity.
- Do not auto-fix without surfacing the diff to the user.

## Verification

- For pre-write: leaf returned `ok` or a non-empty `issues[]` array consumed upstream.
- For post-write: leaf emitted an audit event with its review findings.
