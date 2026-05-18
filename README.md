# pm-second-brain

Personal Second Brain skill-pack for **OpenCode** and **Claude Code**.

Turns any Obsidian vault into a self-evolving knowledge base for product managers.
Markdown-only. No vendor lock-in. Local-first with optional MCP integrations.

## Quick install (macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/AlexGlazkov73/pm-second-brain/main/install.sh | bash
```

This one-liner:

1. Installs Homebrew if missing.
2. Installs `git`, `uv`, `sqlite`, `python@3.12` (skips anything already present).
3. Clones this repo into `~/PM-SecondBrain` (asks before overwriting).
4. Hands off to the interactive [`setup-pm-second-brain.sh`](setup-pm-second-brain.sh)
   which asks for your Obsidian vault path, language, optional cron schedule, etc.

The installer is logged to `/tmp/pm-secondbrain-install-<timestamp>.log`.

**Prerequisite not auto-installed:** [Claude Code CLI](https://docs.claude.com/claude-code)
or [OpenCode](https://opencode.ai) — install whichever runtime you prefer before
or after this script.

### Troubleshooting

- **Re-running the installer:** safe. It detects an existing `~/PM-SecondBrain`
  and offers _update_ / _reinstall (with backup)_ / _cancel_.
- **Where the log is:** `/tmp/pm-secondbrain-install-<timestamp>.log` — full
  stdout + stderr, last line on failure points you to it.
- **Removing everything:** `rm -rf ~/PM-SecondBrain ~/.pm-second-brain` and
  remove symlinks under `~/.claude/skills/` and `~/.opencode/skills/`.

## MCP servers used

- **filesystem-mcp** (community): `npx -y @modelcontextprotocol/server-filesystem <VAULT_ROOT>`
- **pm-sqlite-fts-mcp** (this repo): installed as a console script via `uv`
- **caldav-mcp** / **yandex-tracker-mcp**: user plugs in post-install (optional)

Config templates live in [`mcp-configs/`](mcp-configs/). The installer
substitutes `{{VAULT_ROOT}}` and `{{REPO_ROOT}}` placeholders.

## Architecture decisions

All resolved spike questions from spec §13:

- [ADR-0001: sqlite-fts impl](docs/decisions/0001-sqlite-fts-impl.md)
- [ADR-0002: OpenCode hooks parity](docs/decisions/0002-opencode-hooks-parity.md)
- [ADR-0003: Runtime min versions](docs/decisions/0003-runtime-min-versions.md)
- [ADR-0004: Prompt language](docs/decisions/0004-prompt-language.md)
- [ADR-0005: Stop-the-world evolution](docs/decisions/0005-stop-the-world-evolution.md)

## License

MIT — see [LICENSE](LICENSE).
