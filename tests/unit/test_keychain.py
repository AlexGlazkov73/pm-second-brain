import subprocess

import pytest

from pm_second_brain.keychain import KeychainError, get_secret, store_secret


class FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_fake_security(storage: dict[tuple[str, str], str]):
    def fake_run(cmd, **kw):
        # Simulate the macOS `security` binary
        op = cmd[1]
        if op == "add-generic-password":
            s = cmd[cmd.index("-s") + 1]
            a = cmd[cmd.index("-a") + 1]
            w = cmd[cmd.index("-w") + 1]
            storage[(s, a)] = w
            return FakeResult()
        if op == "find-generic-password":
            s = cmd[cmd.index("-s") + 1]
            a = cmd[cmd.index("-a") + 1]
            if (s, a) in storage:
                return FakeResult(stdout=storage[(s, a)] + "\n")
            return FakeResult(returncode=44, stderr="The specified item could not be found")
        raise AssertionError(f"unexpected op {op}")

    return fake_run


def test_store_then_get_on_macos(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    storage: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(subprocess, "run", _make_fake_security(storage))
    store_secret("pm-second-brain", "anthropic_api_key", "sk-test-123")
    assert get_secret("pm-second-brain", "anthropic_api_key") == "sk-test-123"


def test_missing_raises_on_macos(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(subprocess, "run", _make_fake_security({}))
    with pytest.raises(KeychainError):
        get_secret("pm-second-brain", "nope")


def test_store_then_get_on_linux(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    storage: dict[tuple[str, str], str] = {}

    class FakeKeyring:
        @staticmethod
        def set_password(service, account, secret):
            storage[(service, account)] = secret

        @staticmethod
        def get_password(service, account):
            return storage.get((service, account))

    import pm_second_brain.keychain as kc

    monkeypatch.setattr(kc, "_get_keyring", lambda: FakeKeyring)
    store_secret("pm-second-brain", "anthropic_api_key", "sk-test-linux")
    assert get_secret("pm-second-brain", "anthropic_api_key") == "sk-test-linux"


def test_missing_raises_on_linux(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")

    class FakeKeyring:
        @staticmethod
        def get_password(service, account):
            return None

    import pm_second_brain.keychain as kc

    monkeypatch.setattr(kc, "_get_keyring", lambda: FakeKeyring)
    with pytest.raises(KeychainError):
        get_secret("pm-second-brain", "nope")
