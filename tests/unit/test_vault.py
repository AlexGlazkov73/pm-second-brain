from pathlib import Path

from pm_second_brain.config import Config, Folders, Vault
from pm_second_brain.vault import init_vault


def _cfg(root: Path) -> Config:
    return Config(vault=Vault(root=root), folders=Folders())


def test_init_creates_default_folders(tmp_path: Path) -> None:
    init_vault(_cfg(tmp_path))
    for d in ("mocs", "decisions", "meetings", "daily", "_brain"):
        assert (tmp_path / d).is_dir()


def test_init_writes_brain_templates(tmp_path: Path) -> None:
    init_vault(_cfg(tmp_path))
    assert (tmp_path / "_brain/MEMORY.md").is_file()
    assert (tmp_path / "_brain/USER.md").is_file()
    assert (tmp_path / "_brain/SOUL.md").is_file()


def test_init_writes_moc_index(tmp_path: Path) -> None:
    init_vault(_cfg(tmp_path))
    idx = (tmp_path / "mocs/Index.md").read_text(encoding="utf-8")
    assert "[[Projects]]" in idx


def test_init_idempotent_does_not_overwrite_user_edits(tmp_path: Path) -> None:
    init_vault(_cfg(tmp_path))
    (tmp_path / "_brain/MEMORY.md").write_text("custom user data", encoding="utf-8")
    init_vault(_cfg(tmp_path))
    assert (tmp_path / "_brain/MEMORY.md").read_text(encoding="utf-8") == "custom user data"
