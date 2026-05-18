---
name: pm-research
description: Answer a question about vault content with [[citations]] using MOC routing + FTS5 retrieval. Budget ~5-6k tok in.
version: 0.1.0
author: glazkov222@gmail.com
license: MIT
allowed_tools: ["Read", "fts_search"]
model_preference: primary
inputs: { question: "free-form natural-language question" }
---

# pm-research

## When to Use

When the user asks a question about past vault content (decisions, projects, meetings) and expects an answer grounded in the existing notes with explicit `[[wikilink]]` citations. Input budget ~5-6k tokens.

## Quick Reference

| Field | Value |
|---|---|
| Entry point | `mocs/Index.md` |
| Typical first-hop MOC | `Decisions.md` or `Projects.md` |
| FTS calls | `fts_search(question, limit=10)` |
| Atomic notes opened | Top-3 + ≤2 linked meeting notes |
| Output language | `{{lang}}` |

## Procedure

1. Read `mocs/Index.md`. Decide which MOC is the entry point.
2. Read the chosen MOC (typically `Decisions.md` or `Projects.md`).
3. Run `fts_search(question, limit=10)`.
4. Read top-3 atomic notes from the FTS result, then any `[[meeting links]]` found inside (max 2).
5. Compose an answer with explicit `[[wikilinks]]` to every source actually used.
6. Output language: `{{lang}}`.
7. NEVER fabricate links. If FTS returns nothing relevant, say so.

## Pitfalls

- NEVER fabricate `[[wikilinks]]`. Only cite sources that were actually opened and used.
- If `fts_search` returns nothing relevant, explicitly say so rather than guessing.
- Do not exceed 2 meeting notes follow-ups — keeps the token budget below 5-6k.
- Do not switch output language mid-answer; honor `{{lang}}`.

## Verification

Output format on success:
- 1-paragraph synthesis
- bullet list "Sources: [[a]] [[b]] [[c]]"
- one-line confidence note: "(based on N notes; oldest 2025-12)"

Every `[[wikilink]]` in the answer resolves to a vault path that was actually read during steps 2-4.
