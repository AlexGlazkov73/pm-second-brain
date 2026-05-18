"""Snapshot and revert helpers for skill / MOC files.

A snapshot is a timestamped copy mirrored under ``_brain/_history/<rel>``,
where ``<rel>`` preserves the slice of the target path starting at ``skills/``
or ``mocs/``. Snapshots are immutable; revert copies the most recent snapshot
back onto the live file.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path


_ANCHORS = ("skills", "mocs")


def _mirror_dir(target_file: Path, history_root: Path) -> Path:
    parts = target_file.parts
    for anchor in _ANCHORS:
        if anchor in parts:
            idx = parts.index(anchor)
            rel = Path(*parts[idx:])
            return history_root / rel.parent
    return history_root / target_file.parent.name


def snapshot(target_file: Path, history_root: Path) -> Path:
    """Copy ``target_file`` into the history mirror with a timestamp suffix."""
    mirror = _mirror_dir(target_file, history_root)
    mirror.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    snap = mirror / f"{target_file.stem}-{ts}{target_file.suffix}"
    shutil.copy2(target_file, snap)
    return snap


def list_snapshots(target_file: Path, history_root: Path) -> list[Path]:
    """Return all snapshots for ``target_file``, sorted oldest → newest."""
    mirror = _mirror_dir(target_file, history_root)
    if not mirror.exists():
        return []
    return sorted(mirror.glob(f"{target_file.stem}-*{target_file.suffix}"))


def revert_latest(target_file: Path, history_root: Path) -> Path:
    """Restore the most recent snapshot back onto ``target_file``."""
    snaps = list_snapshots(target_file, history_root)
    if not snaps:
        raise FileNotFoundError(f"No snapshots for {target_file}")
    shutil.copy2(snaps[-1], target_file)
    return snaps[-1]
