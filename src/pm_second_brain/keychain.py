"""Cross-platform secret storage.

macOS path uses the `security(1)` binary (no extra dependency). Linux path
delegates to the `keyring` package (already pulled in by `pyproject.toml`).
"""

from __future__ import annotations

import subprocess
import sys


class KeychainError(Exception):
    """Raised when a secret cannot be stored or retrieved."""


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _get_keyring():  # pragma: no cover - thin import shim
    import keyring  # type: ignore[import-untyped]

    return keyring


def store_secret(service: str, account: str, secret: str) -> None:
    """Persist ``secret`` under ``service/account``."""
    if _is_macos():
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",  # update if exists
                "-s",
                service,
                "-a",
                account,
                "-w",
                secret,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise KeychainError(
                f"security(1) add-generic-password failed: {result.stderr.strip()}"
            )
        return

    _get_keyring().set_password(service, account, secret)


def get_secret(service: str, account: str) -> str:
    """Return the secret stored under ``service/account`` or raise."""
    if _is_macos():
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise KeychainError(f"{service}/{account} not found in macOS Keychain")
        return result.stdout.strip()

    value = _get_keyring().get_password(service, account)
    if value is None:
        raise KeychainError(f"{service}/{account} not found in keyring")
    return value
