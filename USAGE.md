# USAGE — Personal Second Brain v0 (Phases 0-1)

This document covers **what is implemented today** and how to use it.
The full product (skills, hooks, installer, `.pkg`) is in Phases 2-6 — see
[`../tasks/todo.md`](../tasks/todo.md).

---

## What you have today

| Layer                     | Status        | Module / file                                  |
|---------------------------|---------------|------------------------------------------------|
| Typed config loader       | ✅ done       | `pm_second_brain.config`                       |
| Cross-platform Keychain   | ✅ done       | `pm_second_brain.keychain` (macOS + Linux)     |
| Append-only audit log     | ✅ done       | `pm_second_brain.audit`                        |
| Snapshot / revert helper  | ✅ done       | `pm_second_brain.history`                      |
| Vault layout initialiser  | ✅ done       | `pm_second_brain.vault`                        |
| SQLite FTS5 search        | ✅ done       | `pm_second_brain.mcp_servers.sqlite_fts`       |
| MCP stdio server          | ✅ done       | `pm-sqlite-fts-mcp` console script             |
| MCP config templates      | ✅ done       | `mcp-configs/{opencode,claude-code}.json`      |
| Skill-pack (SKILL.md)     | ⏳ Phase 2-3  | —                                              |
| Hooks (PostToolUse…)      | ⏳ Phase 4    | —                                              |
| Installer / `.pkg`        | ⏳ Phase 5    | —                                              |
| Smoke tests / docs        | ⏳ Phase 6    | —                                              |

26 tests pass (`uv run pytest`).

---

## Prerequisites

```bash
# uv (Python project manager) — installs Python 3.11 automatically
curl -LsSf https://astral.sh/uv/install.sh | sh

# install dependencies inside the project
cd pm-second-brain
uv sync --extra dev
```

That's it. Everything else is stdlib (`sqlite3`, `subprocess`, `pathlib`) plus
three pinned deps (`mcp`, `pyyaml`, `keyring`).

---

## Running the tests

```bash
cd pm-second-brain
uv run pytest -v                # full suite (26 tests, ~5s)
uv run pytest tests/unit -v     # unit only (25 tests, ~2s)
uv run pytest tests/integration # MCP stdio test (~8s, spawns subprocess)
```

---

## Scenario 1 — Initialise a vault

You point the helper at any folder. It creates the canonical layout and seeds
the `_brain/` templates without touching anything that already exists.

```python
from pathlib import Path
from pm_second_brain.config import Config, Folders, Vault
from pm_second_brain.vault import init_vault

cfg = Config(vault=Vault(root=Path("~/Obsidian/MyVault").expanduser()))
init_vault(cfg)
```

After running, the vault has:

```
~/Obsidian/MyVault/
├── mocs/{Index,Projects,Decisions,People,Areas}.md
├── decisions/
├── meetings/
├── daily/
└── _brain/{MEMORY,USER,SOUL}.md
```

**Idempotent** — call it again and your edits stay. Safe to run on every
session start.

---

## Scenario 2 — Load a typed config

```yaml
# config.yaml
vault:
  root: "~/Obsidian/MyVault"
language: "ru"
llm:
  primary_model: "claude-sonnet-4-6"
evolution:
  max_patches_per_week: 3
```

```python
from pathlib import Path
from pm_second_brain.config import load_config

cfg = load_config(Path("config.yaml"))
print(cfg.language)              # "ru"
print(cfg.folders.brain)         # "_brain" (default)
print(cfg.cron.daily_brief)      # "0 8 * * 1-5" (default)
print(cfg.llm.primary_model)     # "claude-sonnet-4-6"
```

Missing `vault.root` raises `ConfigError`. All sections fall back to spec
defaults.

---

## Scenario 3 — Store / retrieve a secret

The same call works on both macOS (uses `security(1)`) and Linux (uses
the `keyring` package). PMs never see a terminal — this is called by the
installer.

```python
from pm_second_brain.keychain import store_secret, get_secret, KeychainError

store_secret("pm-second-brain", "anthropic_api_key", "sk-ant-…")

try:
    key = get_secret("pm-second-brain", "anthropic_api_key")
except KeychainError as e:
    print("first run? please paste your key:", e)
```

---

## Scenario 4 — Write an audit event

The audit log is one JSONL file per month under `_brain/audit/`. Each line is
a JSON object with a UTC timestamp prefix. Unicode is preserved verbatim.

```python
from pathlib import Path
from pm_second_brain.audit import audit_append

brain = Path("~/Obsidian/MyVault/_brain").expanduser()
audit_append(brain, {
    "event": "daily-brief-written",
    "tok_in": 3812,
    "tok_out": 1934,
    "skill": "pm-workflow.pm-daily-brief",
})
```

Result: `~/Obsidian/MyVault/_brain/audit/2026-05.jsonl` grows by one line.

---

## Scenario 5 — Snapshot before risky edit, revert if broken

This is what every `pm-meta.pm-evolve` patch will use — snapshot the live
SKILL.md, apply the patch, run a smoke test, revert on failure.

```python
from pathlib import Path
from pm_second_brain.history import snapshot, revert_latest

skill = Path("~/Obsidian/MyVault/_brain/skills/pm-workflow/pm-decision/SKILL.md").expanduser()
history = skill.parents[3] / "_history"   # _brain/_history

# Before patching
snap = snapshot(skill, history)

# ... apply some risky edit ...

# Smoke test fails? roll back to last snapshot:
revert_latest(skill, history)
```

Snapshots are timestamped (`SKILL-20260517-153012.md`) and never overwrite each
other. Listing them returns oldest → newest.

---

## Scenario 6 — Full-text search over the vault

The `FtsStore` class is the unit-testable core. It uses SQLite FTS5 with
`unicode61 remove_diacritics 2` tokenisation, so Cyrillic search works out
of the box.

```python
from pathlib import Path
from pm_second_brain.mcp_servers.sqlite_fts import FtsStore

store = FtsStore(Path("~/Obsidian/MyVault/_brain/sessions.db").expanduser())
store.init_schema()

# Index a note
store.index(
    "decisions/2026-05-17-pricing.md",
    "Tiered pricing",
    "We chose tiered pricing for Q2 because of the SMB segment.",
)

# Search (BM25-ranked)
hits = store.search("pricing Q2", limit=5)
for hit in hits:
    print(hit["path"], "→", hit["snippet"])
# decisions/2026-05-17-pricing.md → We chose tiered «pricing» for «Q2» because…

# Russian works too
store.index("ru.md", "Цена", "Мы выбрали тарифную модель")
print(store.search("тарифную"))
```

---

## Scenario 7 — Run the MCP stdio server

The same `FtsStore` is exposed as an MCP server so OpenCode or Claude Code
can call `fts_search` / `fts_index` / `fts_stats` as tools.

**Manual smoke test:**

```bash
cd pm-second-brain
PM_SQLITE_FTS_DB=/tmp/probe.db uv run pm-sqlite-fts-mcp
# (server blocks on stdin — Ctrl-C to exit)
```

**Wire it into OpenCode / Claude Code** by adding to `~/.opencode/mcp.json` or
`~/.claude/mcp.json` (the installer will do this; for now, copy by hand):

```json
{
  "mcpServers": {
    "pm-sqlite-fts": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/pm-second-brain", "pm-sqlite-fts-mcp"],
      "env": {
        "PM_SQLITE_FTS_DB": "/abs/path/to/vault/_brain/sessions.db"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/abs/path/to/vault"]
    }
  }
}
```

Templates live in [`mcp-configs/`](mcp-configs/) — the Phase 5 installer
substitutes `{{VAULT_ROOT}}` and `{{REPO_ROOT}}`.

Restart your runtime; you should see three new tools: `fts_search`,
`fts_index`, `fts_stats`.

---

## Scenario 8 — End-to-end smoke check (manual, today)

Nothing fancy, just confirms the pieces talk to each other:

```bash
cd pm-second-brain
uv run python - <<'PY'
from pathlib import Path
from pm_second_brain.config import Config, Folders, Vault
from pm_second_brain.vault import init_vault
from pm_second_brain.audit import audit_append
from pm_second_brain.mcp_servers.sqlite_fts import FtsStore

root = Path("/tmp/smoke-vault")
root.mkdir(exist_ok=True)
cfg = Config(vault=Vault(root=root), folders=Folders())

init_vault(cfg)
print("vault initialised:", sorted(p.name for p in root.iterdir()))

store = FtsStore(root / "_brain" / "sessions.db")
store.init_schema()
store.index("daily/2026-05-17.md", "Daily brief",
            "Reviewed pricing Q2 with the SMB segment owner.")
print("search:", store.search("pricing"))

audit_append(root / "_brain", {"event": "smoke-check-ok"})
print("audit lines:", (root / "_brain/audit").glob("*.jsonl"))
PY
```

Expected: lists vault folders, prints one search hit, writes one audit line.

---

## What's not here yet

If a PM tried to use this today, they could:

- ✅ Initialise a vault layout
- ✅ Store API keys safely
- ✅ Search the vault via MCP from OpenCode / Claude Code
- ✅ Log structured audit events
- ❌ Run `pm-workflow.pm-daily-brief` — *skills don't exist yet*
- ❌ Log a decision with `/pm-decision` — *Phase 2*
- ❌ Have the system self-improve via `pm-evolve` — *Phase 4*
- ❌ Install via a `.pkg` double-click — *Phase 5*

The next session should pick up **Phase 2 — Task 14** (four namespace
`SKILL.md` files). That unlocks the first user-visible workflow
(`pm-daily-brief`).

---

## Troubleshooting

| Symptom                                            | Fix                                                                    |
|----------------------------------------------------|------------------------------------------------------------------------|
| `uv: command not found`                            | `curl -LsSf https://astral.sh/uv/install.sh \| sh` then open a new shell |
| `ConfigError: vault.root is required`              | Add a `vault: { root: "..." }` section to `config.yaml`                |
| `KeychainError` on Linux                           | Install `secretstorage`: `uv sync --extra dev` re-installs it          |
| `RuntimeError: PM_SQLITE_FTS_DB env var required`  | Set the env var before spawning `pm-sqlite-fts-mcp`                    |
| MCP server doesn't show in OpenCode                | Restart OpenCode; `tools/list` is read once at session start           |
| FTS query returns zero hits for a known word       | Try lowercasing; `unicode61` is case-insensitive but tokenises on `\W` |
