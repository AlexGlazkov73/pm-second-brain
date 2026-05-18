You are composing a Daily Brief for the owner of this vault.

Output **language**: {{lang}}.

Inputs you have read:
- `mocs/Index.md`, `mocs/Projects.md`, `mocs/Decisions.md`
- Calendar events for {{date}} (may be empty)
- Open tickets (may be empty)
- Yesterday's brief `daily/{{yesterday}}.md` (may be empty)

Produce a brief that:
- Opens with the date and a one-sentence "today's focus" line based on the highest-priority open project.
- Has sections: **Events**, **Open tickets**, **Outstanding action items**, **Notes**.
- Action items must include `[[wikilinks]]` to the project / decision they belong to.
- Skip empty sections rather than rendering placeholder text.
- Keep total length under 400 lines.

After writing, return a short JSON line with `{tok_in, tok_out, files_written, errors}` for the audit log.
