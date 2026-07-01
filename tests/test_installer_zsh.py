"""Tests for DotfilesInstaller.is_zsh — the guard that ensures the installer
runs under zsh before touching the system.

The check inspects the parent process name, but under wrappers like `uv run`
the parent is the wrapper (e.g. `uv`) rather than the shell, so it also falls
back to the $SHELL login shell. get_parent_process_name() may also return None,
which must not crash the check."""

import pytest

from src.installer.installer import DotfilesInstaller


@pytest.fixture
def installer() -> DotfilesInstaller:
    return DotfilesInstaller()


def test_true_when_parent_is_zsh(installer: DotfilesInstaller, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.installer.installer.get_parent_process_name", lambda: "-zsh")
    monkeypatch.delenv("SHELL", raising=False)
    assert installer.is_zsh() is True


def test_true_when_wrapped_but_login_shell_is_zsh(installer: DotfilesInstaller, monkeypatch: pytest.MonkeyPatch):
    # e.g. `uv run -m src.installer`: parent is `uv`, but the user's shell is zsh.
    monkeypatch.setattr("src.installer.installer.get_parent_process_name", lambda: "uv")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert installer.is_zsh() is True


def test_no_crash_when_parent_name_is_none(installer: DotfilesInstaller, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.installer.installer.get_parent_process_name", lambda: None)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert installer.is_zsh() is True


def test_false_when_zsh_missing(installer: DotfilesInstaller, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.installer.installer.get_parent_process_name", lambda: "bash")
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setattr("src.installer.installer.command_exists", lambda _cmd: False)
    assert installer.is_zsh() is False


def test_false_prompts_chsh_when_zsh_available_but_not_active(installer: DotfilesInstaller, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.installer.installer.get_parent_process_name", lambda: "bash")
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setattr("src.installer.installer.command_exists", lambda _cmd: True)
    assert installer.is_zsh() is False
