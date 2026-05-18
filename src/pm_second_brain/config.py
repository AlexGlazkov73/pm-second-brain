"""Typed loader for the user `config.yaml`.

Frozen dataclasses keep configuration immutable at runtime so hooks can't
accidentally mutate shared state. Missing top-level keys fall back to sane
defaults; the only required field is `vault.root`.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when `config.yaml` is missing required fields or malformed."""


@dataclass(frozen=True)
class Folders:
    mocs: str = "mocs"
    decisions: str = "decisions"
    meetings: str = "meetings"
    daily: str = "daily"
    brain: str = "_brain"


@dataclass(frozen=True)
class Vault:
    root: Path


@dataclass(frozen=True)
class LLM:
    provider: str = "anthropic"
    primary_model: str = "claude-sonnet-4-6"
    cheap_model: str = "claude-haiku-4-5"
    prompt_caching: bool = True


@dataclass(frozen=True)
class Evolution:
    safety_gate: bool = True
    auto_apply_trivial: bool = True
    max_patches_per_week: int = 3
    evolve_after_tool_calls: int = 5
    pattern_threshold: float = 0.7


@dataclass(frozen=True)
class Cron:
    daily_brief: str = "0 8 * * 1-5"


@dataclass(frozen=True)
class Config:
    vault: Vault
    folders: Folders = field(default_factory=Folders)
    language: str = "en"
    llm: LLM = field(default_factory=LLM)
    evolution: Evolution = field(default_factory=Evolution)
    cron: Cron = field(default_factory=Cron)


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    val = raw.get(key)
    return val if isinstance(val, dict) else {}


def load_config(path: Path | str) -> Config:
    """Read `config.yaml` and return an immutable :class:`Config`."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    vault = raw.get("vault") or {}
    if "root" not in vault:
        raise ConfigError("vault.root is required in config.yaml")

    return Config(
        vault=Vault(root=Path(vault["root"])),
        folders=Folders(**_section(raw, "folders")),
        language=raw.get("language", "en"),
        llm=LLM(**_section(raw, "llm")),
        evolution=Evolution(**_section(raw, "evolution")),
        cron=Cron(**_section(raw, "cron")),
    )
