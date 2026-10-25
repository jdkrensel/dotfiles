"""Tests for the status line's per-session git cache.

The status line re-reads git at most every 5 seconds and serves a cache file in
between. Its age comes from `stat -f %m`. The fresh-cache test pins that call:
a failed stat falls back to an mtime of 0, which would refresh the cache instead.
The stale-cache test pins the 5-second threshold.
"""

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUSLINE = REPO_ROOT / "src/assets/claude/statusline.sh"

SESSION_ID = "test-session"


def _cache_file(tmp_path: Path) -> Path:
    """The cache path statusline.sh derives for SESSION_ID and tmp_path as cwd."""
    cwd_key = subprocess.run(
        ["bash", "-c", "printf '%s' \"$1\" | cksum | cut -d' ' -f1", "_", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return tmp_path / f"statusline-git-cache-{SESSION_ID}-{cwd_key}"


def _run_statusline(tmp_path: Path) -> str:
    """Run the status line outside any git repo, with HOME and TMPDIR at tmp_path."""
    payload = {
        "model": {"display_name": "Opus 5"},
        "workspace": {"current_dir": str(tmp_path)},
        "session_id": SESSION_ID,
    }
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["TMPDIR"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(STATUSLINE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_fresh_cache_is_served(tmp_path):
    _cache_file(tmp_path).write_text("cached-branch|0|0|\n")

    assert "cached-branch" in _run_statusline(tmp_path)


def test_stale_cache_is_refreshed(tmp_path):
    cache = _cache_file(tmp_path)
    cache.write_text("cached-branch|0|0|\n")
    an_hour_ago = cache.stat().st_mtime - 3600
    os.utime(cache, (an_hour_ago, an_hour_ago))

    # tmp_path is not a git repo, so the refresh finds no branch.
    assert "cached-branch" not in _run_statusline(tmp_path)
