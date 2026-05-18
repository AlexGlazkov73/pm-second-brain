import json
from datetime import datetime, timezone
from pathlib import Path

from pm_second_brain.audit import audit_append, audit_path_for


def test_append_creates_file(tmp_path: Path) -> None:
    brain = tmp_path / "_brain"
    audit_append(brain, {"event": "daily-brief-written", "tok_in": 100})
    files = list((brain / "audit").glob("*.jsonl"))
    assert len(files) == 1


def test_each_line_has_ts(tmp_path: Path) -> None:
    brain = tmp_path / "_brain"
    audit_append(brain, {"event": "x"})
    audit_append(brain, {"event": "y"})
    f = next((brain / "audit").glob("*.jsonl"))
    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert "ts" in obj
        # ISO 8601 with Z suffix parses correctly
        datetime.fromisoformat(obj["ts"].replace("Z", "+00:00"))


def test_path_for_returns_monthly_file(tmp_path: Path) -> None:
    brain = tmp_path / "_brain"
    p = audit_path_for(brain, datetime(2026, 5, 17, tzinfo=timezone.utc))
    assert p.name == "2026-05.jsonl"


def test_unicode_preserved(tmp_path: Path) -> None:
    brain = tmp_path / "_brain"
    audit_append(brain, {"event": "decision", "title": "Тарифы Q2"})
    f = next((brain / "audit").glob("*.jsonl"))
    content = f.read_text(encoding="utf-8")
    assert "Тарифы" in content
