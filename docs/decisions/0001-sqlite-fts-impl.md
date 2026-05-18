# ADR 0001 — sqlite-fts MCP implementation choice

**Status:** Accepted (2026-05-17)
**Spike task:** Task 3 (Phase 0)

## Context

Spec §13 leaves open the question of how to expose SQLite FTS5 search to the agent:
a thin bash wrapper around `sqlite3 -json`, or a Python stdio MCP server that uses
the official `mcp` SDK and `sqlite3` stdlib.

## Decision

**Custom Python stdio MCP server** using the official Anthropic `mcp` SDK and
Python's `sqlite3` stdlib (which has bundled FTS5 since 3.9).

## Reasoning

- A bash wrapper is fragile for structured tool arguments — FTS5 query operators,
  `snippet()` config, and BM25 ranking all want typed parameters.
- Python stdlib `sqlite3` ships FTS5 by default on every modern interpreter; no
  extra system dependency.
- Testable end-to-end with `pytest` and `asyncio.subprocess` (see
  `tests/integration/test_mcp_stdio.py`).
- Ships as a single `uv`-managed console script (`pm-sqlite-fts-mcp`).

## MCP tool surface (implemented in Tasks 11-12)

| Tool          | Args                                                | Returns                                   |
|---------------|-----------------------------------------------------|-------------------------------------------|
| `fts_search`  | `query: str`, `limit: int = 10`                     | `[{path, title, snippet, rank}, ...]`     |
| `fts_index`   | `path: str`, `title: str`, `body: str`              | `{ok: bool}`                              |
| `fts_reindex` | `vault_root: str`                                   | `{indexed: int}` *(Phase 2+)*             |
| `fts_stats`   | —                                                   | `{note_count, last_index_ts}`             |

Schema uses `tokenize = 'unicode61 remove_diacritics 2'` so Russian/Cyrillic
matches work without extra tokenizer config.

## Verification status

- [x] Python `sqlite3` exposes FTS5 (verified locally on Python 3.11.13)
- [ ] **TODO:** Russian unicode61 query confirmed end-to-end against a real vault
      (covered by `test_unicode_russian` in `tests/unit/test_sqlite_fts.py`)
