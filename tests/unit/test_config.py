from pathlib import Path

import pytest

from pm_second_brain.config import Config, ConfigError, load_config

FIXTURES = Path(__file__).parent.parent / "fixtures" / "config"


def test_load_valid_config() -> None:
    cfg = load_config(FIXTURES / "valid.yaml")
    assert isinstance(cfg, Config)
    assert cfg.vault.root == Path("/tmp/test-vault")
    assert cfg.folders.mocs == "mocs"
    assert cfg.language == "ru"
    assert cfg.llm.primary_model == "claude-sonnet-4-6"
    assert cfg.evolution.max_patches_per_week == 3


def test_missing_vault_raises() -> None:
    with pytest.raises(ConfigError, match="vault.root"):
        load_config(FIXTURES / "missing-vault.yaml")


def test_defaults_applied() -> None:
    cfg = load_config(FIXTURES / "valid.yaml")
    assert cfg.folders.brain == "_brain"
    assert cfg.cron.daily_brief == "0 8 * * 1-5"
