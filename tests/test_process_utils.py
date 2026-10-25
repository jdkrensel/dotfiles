"""Tests for get_parent_process_name, which is_zsh relies on to spot the shell."""

import subprocess

import pytest

from installer.utils import process


def test_asks_ps_for_the_parent_pid(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_check_output(command, **_kwargs):
        calls.append(command)
        return "-zsh\n"

    monkeypatch.setattr(process.os, "getppid", lambda: 4242)
    monkeypatch.setattr(process.subprocess, "check_output", fake_check_output)

    assert process.get_parent_process_name() == "-zsh"
    assert calls == [["ps", "-p", "4242", "-o", "comm="]]


@pytest.mark.parametrize("error", [subprocess.CalledProcessError(1, "ps"), FileNotFoundError("ps")])
def test_none_when_ps_fails(monkeypatch: pytest.MonkeyPatch, error: Exception):
    def failing_check_output(_command, **_kwargs):
        raise error

    monkeypatch.setattr(process.subprocess, "check_output", failing_check_output)
    assert process.get_parent_process_name() is None
