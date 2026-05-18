# ADR 0004 — Prompt language policy

**Status:** Accepted (2026-05-17)
**Spike task:** Task 4 (Phase 0)

## Decision

- **SKILL.md** and **prompt.md** bodies: **English** only.
- User-facing narrative output language: driven by `config.yaml: language` and
  injected into prompts as the `{{lang}}` placeholder. Accepted values: `ru`, `en`.
  Default: `en`.

## Reasoning

- Claude follows English instruction text more faithfully than non-English
  instructions; mixing languages inside a prompt is a known reliability drag.
- Output language is a *runtime variable* — the same English skill can speak
  any language as long as the prompt template parameterises it.
- A single `{{lang}}` knob makes localisation trivially auditable: change
  one YAML value, every leaf skill produces output in the new language.

## How leaf skills use `{{lang}}`

In `prompt.md`:

```markdown
Output **language**: {{lang}}.
You are composing ...
```

The hook layer or skill loader substitutes `{{lang}}` from
`config.yaml: language` before passing the prompt to the model.

## Out of scope for v0

- Multi-language vaults (one vault → one language).
- Auto-detecting language from user input.
- Translating MOC titles or template content.
