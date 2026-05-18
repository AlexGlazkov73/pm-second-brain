"""SQLite FTS5 search exposed both as a Python class and as a stdio MCP server.

The :class:`FtsStore` class is pure Python and trivial to unit-test. The
``main()`` entrypoint wraps it as an MCP stdio server using the official
``mcp`` SDK, exposing three tools: ``fts_search``, ``fts_index``, ``fts_stats``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
  path UNINDEXED,
  title,
  body,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


class FtsStore:
    """Thin wrapper around an FTS5 virtual table.

    Construction is cheap (no I/O); call :meth:`init_schema` before the
    first read/write to create the database file and schema.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(SCHEMA)

    def index(self, path: str, title: str, body: str) -> None:
        """Index (or replace) the note identified by ``path``."""
        with self._connect() as con:
            con.execute("DELETE FROM notes_fts WHERE path = ?", (path,))
            con.execute(
                "INSERT INTO notes_fts(path, title, body) VALUES (?, ?, ?)",
                (path, title, body),
            )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Run an FTS5 MATCH query and return BM25-ranked hits."""
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT path, title,
                       snippet(notes_fts, 2, '«', '»', '...', 8) AS snippet,
                       bm25(notes_fts) AS rank
                FROM notes_fts
                WHERE notes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def stats(self) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT COUNT(*) AS c FROM notes_fts").fetchone()
            return {"note_count": row["c"]}


# ---------------------------------------------------------------------------
# MCP stdio server entrypoint
# ---------------------------------------------------------------------------

_STORE: FtsStore | None = None


def _store() -> FtsStore:
    global _STORE
    if _STORE is None:
        db = os.environ.get("PM_SQLITE_FTS_DB")
        if not db:
            raise RuntimeError("PM_SQLITE_FTS_DB env var is required")
        _STORE = FtsStore(Path(db))
        _STORE.init_schema()
    return _STORE


def main() -> None:  # pragma: no cover - exercised by integration tests
    """Run the MCP stdio server (blocks on stdin/stdout)."""
    import asyncio

    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    server: Server = Server("pm-sqlite-fts")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return [
            Tool(
                name="fts_search",
                description="BM25 FTS5 search across indexed notes",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="fts_index",
                description="Index a single note (replaces existing path)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["path", "title", "body"],
                },
            ),
            Tool(
                name="fts_stats",
                description="Return index statistics",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        s = _store()
        if name == "fts_search":
            rows = s.search(arguments["query"], arguments.get("limit", 10))
            return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False))]
        if name == "fts_index":
            s.index(arguments["path"], arguments["title"], arguments["body"])
            return [TextContent(type="text", text=json.dumps({"ok": True}))]
        if name == "fts_stats":
            return [TextContent(type="text", text=json.dumps(s.stats()))]
        raise ValueError(f"unknown tool: {name}")

    async def _run() -> None:
        async with stdio_server() as (reader, writer):
            await server.run(reader, writer, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
