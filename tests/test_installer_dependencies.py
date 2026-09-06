"""Tests for SystemDependencyManager's curl-based installers.

These never run curl. Every test patches ``run_command`` and ``command_exists``
in the installer module's namespace and asserts on the command string that would
have been issued, because the command string is where the behaviour lives: which
flags are passed, and whether the step is skipped at all.

The opencode case carries the most detail. Its vendor script resolves the release
version through api.github.com, which is rate-limited per source IP and fails
behind a VPN or shared NAT, so the version is resolved here from the releases
redirect and passed in explicitly — with the plain invocation as a fallback."""

import subprocess

import pytest

from src.installer import installer as installer_module
from src.installer.installer import SystemDependencyManager
from src.installer.printer import Printer


@pytest.fixture
def commands(monkeypatch):
    """Record every command run, and report every binary as missing by default."""
    recorded: list[str] = []

    def fake_run(command: str, **kwargs) -> subprocess.CompletedProcess:
        recorded.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(installer_module, "run_command", fake_run)
    monkeypatch.setattr(installer_module, "command_exists", lambda command: False)
    return recorded


@pytest.fixture
def manager() -> SystemDependencyManager:
    return SystemDependencyManager(Printer())


def _installed(monkeypatch, name: str) -> None:
    monkeypatch.setattr(installer_module, "command_exists", lambda command: command == name)


def _fail_on(monkeypatch, recorded: list[str], substring: str) -> None:
    """Make any command containing ``substring`` raise, as a failed curl would."""

    def fake_run(command: str, **kwargs) -> subprocess.CompletedProcess:
        recorded.append(command)
        if substring in command:
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(installer_module, "run_command", fake_run)


def _stdout_for(monkeypatch, recorded: list[str], substring: str, stdout: str) -> None:
    """Return ``stdout`` from commands containing ``substring``, empty otherwise."""

    def fake_run(command: str, **kwargs) -> subprocess.CompletedProcess:
        recorded.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=stdout if substring in command else "", stderr="")

    monkeypatch.setattr(installer_module, "run_command", fake_run)


# --- already-installed short-circuits ------------------------------------


@pytest.mark.parametrize(
    ("binary", "method"),
    [
        ("opencode", "install_opencode"),
        ("claude", "install_claude"),
        ("uv", "install_uv"),
        ("cargo", "install_rust"),
    ],
)
def test_present_binary_runs_nothing(manager, commands, monkeypatch, binary, method):
    _installed(monkeypatch, binary)
    assert getattr(manager, method)() is True
    assert commands == []


# --- opencode ------------------------------------------------------------


def test_opencode_resolves_version_before_installing(manager, commands, monkeypatch):
    _stdout_for(
        monkeypatch,
        commands,
        "releases/latest",
        "https://github.com/anomalyco/opencode/releases/tag/v1.18.29\n",
    )
    assert manager.install_opencode() is True
    assert commands[0].endswith(installer_module.OPENCODE_LATEST_RELEASE_URL)
    assert commands[1] == (
        f"curl -fsSL {installer_module.OPENCODE_INSTALL_URL} | bash -s -- --no-modify-path --version 1.18.29"
    )


def test_opencode_passes_the_resolved_version_instead_of_the_api(manager, commands, monkeypatch):
    """Resolving here is what keeps the rate-limited API path out of the install.

    This asserts on the command we issue, not on what the vendor script then does:
    in the fallback below, with no version to pass, the script does reach the API —
    deliberately, since that may still work from the machine in question."""
    _stdout_for(monkeypatch, commands, "releases/latest", ".../releases/tag/v1.18.29\n")
    manager.install_opencode()
    assert not any("api.github.com" in command for command in commands)


def test_opencode_leaves_the_shell_config_alone(manager, commands):
    """~/.zshrc is a symlink into this repo; the script must not append to it."""
    manager.install_opencode()
    assert all("--no-modify-path" in command for command in commands if "bash -s" in command)


def test_opencode_installs_without_a_version_when_resolution_returns_nothing(manager, commands):
    """An empty redirect body is not fatal — the script resolves the version itself."""
    assert manager.install_opencode() is True
    assert commands[-1] == (
        f"curl -fsSL {installer_module.OPENCODE_INSTALL_URL} | bash -s -- --no-modify-path"
    )


def test_opencode_installs_without_a_version_when_resolution_fails(manager, commands, monkeypatch):
    _fail_on(monkeypatch, commands, "releases/latest")
    assert manager.install_opencode() is True
    assert commands[-1].endswith("--no-modify-path")


def test_opencode_reports_a_failed_install(manager, commands, monkeypatch, capsys):
    _fail_on(monkeypatch, commands, "opencode.ai/install")
    assert manager.install_opencode() is False
    assert "Failed to install opencode" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("redirect", "expected"),
    [
        ("https://github.com/anomalyco/opencode/releases/tag/v1.18.29\n", "1.18.29"),
        ("https://github.com/anomalyco/opencode/releases/tag/1.18.29", "1.18.29"),  # tag without the v
        ("https://github.com/anomalyco/opencode/releases/latest", None),  # no redirect followed
        ("", None),
        # The tag reaches a shell command, so anything not version-shaped is dropped.
        ("https://github.com/x/y/releases/tag/v1.0; rm -rf ~", None),
        ("https://github.com/x/y/releases/tag/v`whoami`", None),
        ("https://github.com/x/y/releases/tag/v", None),
    ],
)
def test_latest_opencode_version_parses_the_redirect(manager, commands, monkeypatch, redirect, expected):
    _stdout_for(monkeypatch, commands, "releases/latest", redirect)
    assert manager.latest_opencode_version() == expected


# --- the other curl installers -------------------------------------------


def test_claude_uses_its_native_installer(manager, commands):
    assert manager.install_claude() is True
    assert commands == ["curl -fsSL https://claude.ai/install.sh | bash"]


def test_uv_puts_its_bin_dir_on_path(manager, commands, monkeypatch):
    """`uv tool install` runs later in the same process, so PATH must be updated now."""
    monkeypatch.setenv("PATH", "/usr/bin")
    assert manager.install_uv() is True
    assert commands == ["curl -LsSf https://astral.sh/uv/install.sh | sh"]
    assert str(installer_module.Path.home() / ".local" / "bin") in installer_module.os.environ["PATH"]


def test_failed_dependency_stops_the_phase(manager, commands, monkeypatch, capsys):
    """install_system_dependencies is an `and` chain: nothing runs past a failure.

    Claude Code is the step before opencode, and one that reports failure by
    returning False rather than raising."""
    _fail_on(monkeypatch, commands, "claude.ai/install.sh")
    assert manager.install_system_dependencies() is False
    assert not any("opencode" in command for command in commands)
