import time
from pathlib import Path

import pytest

from pm_second_brain.history import list_snapshots, revert_latest, snapshot


def _make_skill(tmp_path: Path, content: str = "v1") -> Path:
    skill = tmp_path / "_brain/skills/pm-workflow/pm-decision/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(content, encoding="utf-8")
    return skill


def test_snapshot_creates_timestamped_copy(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    snap = snapshot(skill, tmp_path / "_brain/_history")
    assert snap.exists()
    assert snap.read_text(encoding="utf-8") == "v1"
    assert "SKILL-" in snap.name and snap.name.endswith(".md")


def test_revert_restores_latest(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    snapshot(skill, tmp_path / "_brain/_history")
    skill.write_text("v2-broken", encoding="utf-8")
    revert_latest(skill, tmp_path / "_brain/_history")
    assert skill.read_text(encoding="utf-8") == "v1"


def test_list_returns_chronological(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    snapshot(skill, tmp_path / "_brain/_history")
    time.sleep(1.05)  # filename has second-resolution timestamp
    skill.write_text("v2", encoding="utf-8")
    snapshot(skill, tmp_path / "_brain/_history")
    snaps = list_snapshots(skill, tmp_path / "_brain/_history")
    assert len(snaps) == 2
    assert snaps[0].name < snaps[1].name


def test_revert_with_no_snapshots_raises(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    with pytest.raises(FileNotFoundError):
        revert_latest(skill, tmp_path / "_brain/_history")
