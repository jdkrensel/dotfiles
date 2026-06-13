"""Tests for the PreToolUse hook that gates package installs and remote git ops.

The hook returns permissionDecision "ask" (never a hard block), so substring
matches err toward asking — that's intentional and low-cost.
"""

import json

import pytest

DANGEROUS = [
    "pip install requests",
    "pip3 uninstall foo",
    "pipx install black",
    "uv add pydantic",
    "uv remove click",
    "uv pip install numpy",
    "uv tool install ruff",
    "brew install jq",
    "brew upgrade",
    "brew uninstall wget",
    "apt install vim",
    "apt-get remove nano",
    "sudo npm install -g typescript",
    "npm install --global yarn",
    "pnpm add -g pm2",
    "yarn global add serve",
    "gem install bundler",
    "cargo install ripgrep",
    "go install example.com/cmd@latest",
    "git push origin main",
    "git pull",
    "git fetch --all",
    "git rebase main",
]

BENIGN = [
    "ls -la",
    "git status",
    "git diff HEAD",
    "git log --oneline -10",
    "git commit -m 'wip'",
    "git add -A",
    "npm install lodash",
    "npm run build",
    "cargo build --release",
    "go build ./...",
    "cat pyproject.toml",
    "python script.py",
]


@pytest.mark.parametrize("cmd", DANGEROUS)
def test_dangerous_commands_ask(run_hook, cmd):
    result = run_hook("block_dangerous_commands.py", {"tool_input": {"command": cmd}})
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


@pytest.mark.parametrize("cmd", BENIGN)
def test_benign_commands_noop(run_hook, cmd):
    result = run_hook("block_dangerous_commands.py", {"tool_input": {"command": cmd}})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_missing_command_field_noop(run_hook):
    result = run_hook("block_dangerous_commands.py", {"tool_input": {}})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_malformed_json_is_safe(run_hook_raw):
    result = run_hook_raw("block_dangerous_commands.py", "not json at all")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
