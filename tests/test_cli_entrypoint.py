"""Tests for argument parsing at the entry point.

Two things matter here and neither is cosmetic: `python3 -m src.installer` with
no subcommand must keep running a full install, as it always has, and --dry-run
must be honored wherever it appears. argparse resets a subparser's defaults over
the parent's, so a regression in that setup would silently turn `--dry-run
install` into a real install."""

import pytest

from src.installer.__main__ import build_parser, main


@pytest.mark.parametrize(("argv", "expected"), [([], None), (["install"], "install")])
def test_no_subcommand_and_install_both_mean_install(argv, expected):
    args = build_parser().parse_args(argv)
    assert args.command == expected
    assert args.dry_run is False


@pytest.mark.parametrize("argv", [["--dry-run"], ["install", "--dry-run"], ["--dry-run", "install"]])
def test_dry_run_is_honored_in_every_position(argv):
    assert build_parser().parse_args(argv).dry_run is True


@pytest.mark.parametrize("command", ["resolve", "plan", "doctor"])
def test_read_only_commands_never_dry_run(command):
    """They write nothing by definition, so none of them defines the flag."""
    args = build_parser().parse_args([command])
    assert args.command == command
    assert args.dry_run is False


@pytest.mark.parametrize("command", ["resolve", "plan", "doctor"])
def test_read_only_commands_reject_a_trailing_dry_run(command):
    """Only `install` defines it, so `resolve --dry-run` is a parse error rather
    than a flag that quietly does nothing. (In the prefix position it is still
    accepted and ignored — that is the top-level flag, not this one.)"""
    with pytest.raises(SystemExit):
        build_parser().parse_args([command, "--dry-run"])


@pytest.mark.parametrize("command", ["resolve", "plan"])
def test_group_defaults_to_the_whole_tree(command):
    assert build_parser().parse_args([command]).group is None


@pytest.mark.parametrize("command", ["resolve", "plan"])
def test_group_can_narrow_to_one_collection(command):
    assert build_parser().parse_args([command, "--group", "rules"]).group == "rules"


def test_doctor_takes_no_group():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["doctor", "--group", "rules"])


def test_an_unknown_subcommand_is_rejected():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["bogus"])


def test_group_must_name_a_real_collection():
    """A typo would otherwise resolve to an empty plan, indistinguishable from a
    collection that genuinely has nothing in it."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["resolve", "--group", "rule"])


# --- dispatch ----------------------------------------------------------------


class _Recorder:
    """Stands in for a command's run(), recording how it was called."""

    def __init__(self, exit_code: int = 0):
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.exit_code = exit_code

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.exit_code


@pytest.mark.parametrize("command", ["resolve", "plan", "doctor"])
def test_each_read_only_command_dispatches_to_its_module(command, monkeypatch):
    recorder = _Recorder(exit_code=7)
    monkeypatch.setattr(f"src.installer.__main__.{command}.run", recorder)

    assert main([command]) == 7  # the command's own exit code reaches the shell
    assert len(recorder.calls) == 1


@pytest.mark.parametrize("command", ["resolve", "plan"])
def test_the_group_flag_reaches_the_command(command, monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(f"src.installer.__main__.{command}.run", recorder)

    main([command, "--group", "rules"])
    args, _ = recorder.calls[0]
    assert args[1] == "rules"


@pytest.mark.parametrize(("argv", "dry_run"), [([], False), (["install"], False), (["--dry-run"], True)])
def test_install_is_the_default_and_carries_the_dry_run_flag(argv, dry_run, monkeypatch):
    """The invariant the entry point exists to preserve: bare `python3 -m
    src.installer` still runs a real install."""
    built: list[bool] = []

    class _Installer:
        def __init__(self, dry_run: bool = False):
            built.append(dry_run)

        def run(self) -> bool:
            return True

    monkeypatch.setattr("src.installer.__main__.DotfilesInstaller", _Installer)
    assert main(argv) == 0
    assert built == [dry_run]


def test_a_failed_install_exits_non_zero(monkeypatch):
    class _Installer:
        def __init__(self, dry_run: bool = False):
            pass

        def run(self) -> bool:
            return False

    monkeypatch.setattr("src.installer.__main__.DotfilesInstaller", _Installer)
    assert main([]) == 1


def test_an_unhandled_error_is_logged_and_exits_non_zero(monkeypatch):
    """A traceback should not reach the user as a crash."""
    def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("src.installer.__main__.doctor.run", _boom)
    assert main(["doctor"]) == 1
