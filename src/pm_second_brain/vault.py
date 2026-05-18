"""Idempotent vault layout initialiser.

Creates the canonical folder structure under ``cfg.vault.root`` and copies
the markdown templates from ``templates/`` into the live vault. Existing user
edits are never overwritten — only missing files are created.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .config import Config


# Repo-relative templates dir. ``parents[2]`` walks up
# `src/pm_second_brain/vault.py` -> repo root.
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def init_vault(cfg: Config) -> None:
    """Create folders + seed templates under ``cfg.vault.root``."""
    root = cfg.vault.root
    root.mkdir(parents=True, exist_ok=True)

    for folder in (
        cfg.folders.mocs,
        cfg.folders.decisions,
        cfg.folders.meetings,
        cfg.folders.daily,
        cfg.folders.brain,
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)

    _copy_tree(TEMPLATES_DIR / "_brain", root / cfg.folders.brain, overwrite=False)
    _copy_tree(TEMPLATES_DIR / "mocs", root / cfg.folders.mocs, overwrite=False)


def _copy_tree(src: Path, dst: Path, overwrite: bool) -> None:
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists() and not overwrite:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
