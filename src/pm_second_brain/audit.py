"""Append-only JSONL audit log.

One file per month at ``<brain_dir>/audit/<YYYY-MM>.jsonl``. Every line is one
JSON object with a stable ``ts`` field (ISO-8601 UTC with ``Z`` suffix). Unicode
is preserved verbatim so Cyrillic vault content stays readable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def audit_path_for(brain_dir: Path, when: datetime | None = None) -> Path:
    """Return the audit-log path for the given month (defaults to UTC now)."""
    when = when or datetime.now(timezone.utc)
    audit_dir = brain_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir / f"{when.strftime('%Y-%m')}.jsonl"


def audit_append(brain_dir: Path, event: dict[str, Any]) -> None:
    """Append ``event`` to this month's audit log, prefixing a UTC timestamp."""
    when = datetime.now(timezone.utc)
    payload = {"ts": when.isoformat().replace("+00:00", "Z"), **event}
    path = audit_path_for(brain_dir, when)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
