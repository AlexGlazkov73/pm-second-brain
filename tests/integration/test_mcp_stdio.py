import asyncio
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_mcp_list_tools(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"
    env = os.environ.copy()
    env["PM_SQLITE_FTS_DB"] = str(db)

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pm_second_brain.mcp_servers.sqlite_fts",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    try:
        # initialize handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        }
        proc.stdin.write((json.dumps(init_req) + "\n").encode())
        await proc.stdin.drain()
        init_line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        init_resp = json.loads(init_line)
        assert init_resp["id"] == 1 and "result" in init_resp

        # initialized notification
        initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write((json.dumps(initialized) + "\n").encode())
        await proc.stdin.drain()

        # tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        proc.stdin.write((json.dumps(list_req) + "\n").encode())
        await proc.stdin.drain()
        list_line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        list_resp = json.loads(list_line)
        names = {t["name"] for t in list_resp["result"]["tools"]}
        assert {"fts_search", "fts_index", "fts_stats"} <= names
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
