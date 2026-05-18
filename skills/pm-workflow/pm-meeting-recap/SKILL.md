---
name: pm-meeting-recap
description: (v1 — not active in v0) Summarize a meeting transcript into a structured meeting note. Activated when IMAP/Telemost MCP is configured.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "Write"]
model_preference: primary
status: skeleton
---

# pm-meeting-recap (skeleton)

## When to Use

v1 placeholder; activated when IMAP/Telemost MCP is configured. In v0 this skill is intentionally inactive and must not be invoked. Implementation lands in v1 when IMAP and Telemost MCP servers are added.

## Quick Reference

| Field | Value |
|---|---|
| Status | skeleton (v0) |
| Activation prerequisite | IMAP and Telemost MCP servers configured |
| Trigger (v1) | User pastes a transcript or IMAP MCP delivers one |
| Output (v1) | `meetings/<YYYY-MM-DD>-<slug>.md` |
| Hand-off (v1) | Decisions → `pm-knowledge.pm-add-decision` |

## Procedure

1. (v1) Receive transcript from user paste or IMAP MCP delivery.
2. (v1) Parse the transcript into structured fields: Participants, Decisions, Action items (each with owner + due date), Open questions.
3. (v1) Render meeting note at `meetings/<YYYY-MM-DD>-<slug>.md`.
4. (v1) Hand off any "Decisions" entries to `pm-knowledge.pm-add-decision`.
5. (v0) Do nothing — return a "not active in v0" message to the caller.

## Pitfalls

- Do not invoke this skill in v0. The dispatcher (`pm-workflow`) lists it as a future trigger only.
- Do not fabricate participants, decisions, or action items if the transcript is incomplete; leave the corresponding section empty.
- Do not write the decision note directly from this skill — always delegate via `pm-knowledge.pm-add-decision`.

## Verification

- (v1) `meetings/<YYYY-MM-DD>-<slug>.md` exists with the four expected sections.
- (v1) Every "Decisions" entry triggered exactly one `pm-add-decision` invocation.
- (v0) Caller received an explicit "skill inactive in v0" response.
