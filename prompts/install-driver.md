# Install-driver prompt — pm-second-brain v0

**Purpose.** This prompt makes an agent (Claude Code / OpenCode) install the
pm-second-brain skill-pack on the current machine. The agent uses
`AskUserQuestion` to gather inputs, then feeds them via stdin to
`setup-pm-second-brain.sh` so the user never deals with a raw terminal prompt.

**Use it like this.** Paste this whole file as a user message into Claude Code
or OpenCode, sitting in the repo root that contains `pm-second-brain/`. The
agent will drive the rest.

---

## Agent instructions (read carefully)

You are installing the pm-second-brain skill-pack. Follow these steps in order.
Do not improvise — the installer's `read` calls expect input in a specific
sequence.

### Step 1 — Locate the installer

Run:

```bash
ls pm-second-brain/setup-pm-second-brain.sh
```

If it is missing, stop and tell the user where you are and what is missing.

### Step 2 — Verify prerequisites silently

Run:

```bash
for c in bash python3 sqlite3 uv; do command -v "$c" >/dev/null || echo "MISSING: $c"; done
```

If anything prints `MISSING:`, stop and ask the user to install it (suggest
`brew install uv` for uv).

### Step 3 — Collect inputs via `AskUserQuestion`

Ask **all four questions in a single `AskUserQuestion` call** so the user sees
them as one form. Use these exact `header` values: `Vault path`, `Language`,
`Cron`, `Launchd`.

1. **Vault path** — absolute path to the user's Obsidian vault. Offer two
   sensible defaults plus "Other" (the AskUserQuestion tool injects Other
   automatically):
   - `~/Documents/Obsidian/PM-SecondBrain` (will be created)
   - `~/Documents/Obsidian` (existing top-level Obsidian folder, if present)

   When the user picks an existing label, expand `~` to `$HOME` yourself before
   piping. When the user picks Other, accept whatever absolute path they typed.

2. **Language** — `ru` (Recommended) or `en`. Single-select.

3. **Cron** — daily-brief schedule. Single-select:
   - `0 8 * * 1-5` (08:00 Mon–Fri, Recommended)
   - `0 9 * * 1-5` (09:00 Mon–Fri)
   - `0 8 * * *` (08:00 every day)
   - Other (free-form cron expression)

4. **Launchd** — install macOS launchd schedule now? `Yes (Recommended)` /
   `No, I'll do it later`. Only ask on macOS (`uname -s` returns `Darwin`).
   On Linux, default this to `No` and skip the question.

### Step 4 — Compute the stdin script

The installer reads in this order:

| read # | Prompt                                | Always asked?            |
|--------|---------------------------------------|--------------------------|
| 1      | Vault path                            | yes                      |
| 2      | "Create $VAULT_ROOT?" (y/N)           | only if dir is missing   |
| 3      | Output language                       | yes                      |
| 4      | Daily brief cron                      | yes                      |
| 5      | "Install macOS launchd schedule now?" | only on macOS            |

Before piping, decide whether prompts 2 and 5 will fire:

```bash
VAULT="<expanded absolute path>"
DIR_EXISTS=$([[ -d "$VAULT" ]] && echo 1 || echo 0)
IS_MAC=$([[ "$(uname -s)" == "Darwin" ]] && echo 1 || echo 0)
```

Build the stdin payload (one answer per line, in the order above; skip the
optional lines that won't be asked):

```bash
{
  echo "$VAULT"
  [[ "$DIR_EXISTS" == 0 ]] && echo "y"   # auto-confirm creation
  echo "$LANG"                            # ru or en
  echo "$CRON"                            # e.g. 0 8 * * 1-5
  [[ "$IS_MAC" == 1 ]] && echo "$LAUNCHD" # y or n
} | bash pm-second-brain/setup-pm-second-brain.sh
```

Stream the installer's stdout/stderr back to the user verbatim. Do **not**
swallow output — the user wants to see `✓` lines as they happen.

### Step 5 — Verify the install

After the script returns, run these checks and report each:

```bash
test -f "$HOME/.pm-second-brain/config.yaml" && echo "config OK"
test -f "$VAULT/_brain/sessions.db" && echo "fts db OK"
ls -la "$HOME/.opencode/skills" | grep pm- || echo "WARN: no opencode skill links"
ls -la "$HOME/.claude/skills"   | grep pm- || echo "WARN: no claude skill links"
test -f "$HOME/.opencode/mcp.json" && echo "opencode mcp OK"
test -f "$HOME/.claude/mcp.json"   && echo "claude mcp OK"
```

On macOS, if launchd was requested, also:

```bash
launchctl list | grep com.pm-second-brain.daily-brief || echo "WARN: launchd job not loaded"
```

### Step 6 — Tell the user how to try it

Print exactly:

```
Готово. Попробуй:
  OpenCode:    opencode run --skill pm-workflow.pm-daily-brief
  Claude Code: /pm-workflow.pm-daily-brief
Vault: <VAULT>
Config: ~/.pm-second-brain/config.yaml
```

---

## Constraints

- **Don't ask the user about the Anthropic API key.** OpenCode and Claude Code
  each carry their own provider auth. The installer no longer touches the
  keychain for this.
- **Don't hardcode any path.** The vault path must come from the user via
  AskUserQuestion in Step 3.
- **Don't run `git init` or `git commit`** anywhere inside `pm-second-brain/`.
  This skill-pack ships through the installer, not through git.
- **Don't add `--no-verify` or skip hooks.** If the installer fails, surface
  the error to the user — do not retry by bypassing safety.
- If `command -v opencode` returns nothing, the installer will skip the
  launchd step on its own with a warning. That is fine; do not try to install
  opencode yourself.
