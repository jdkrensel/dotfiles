# dotfiles

A Python installer (`installer/`) that symlinks tracked assets (`assets/`)
into `$HOME`, merges Claude settings, and installs system dependencies. Run it with
`uv run -m installer`; `--dry-run` previews the configuration phase.

## Tests

The suite is pytest under `tests/`, one file per installer concern
(`test_installer_symlinks.py`, `test_resolver.py`, …). Run it with `uv run pytest`.

Three rules, in the order they come up:

- **Run the relevant tests before modifying code.** A baseline distinguishes a
  failure you caused from one that was already there. If something is already
  failing, say so before making changes.
- **New code ships with tests in the same change.** A new function, class, or
  command is not done until the suite covers it.
- **Missing coverage on code you touch gets written, not skipped.** When the area
  you are changing has no tests, add them rather than noting the gap and moving on.

Tests must not touch the real `$HOME`, the network, or the machine's package
managers. Drive the filesystem through `tmp_path`, and patch `run_command` /
`command_exists` in the module under test to assert on the command string that
would have been issued — `tests/test_installer_dependencies.py` is the pattern.

## Assets

Any file under `assets/` can be overridden per machine by a copy at the same
relative path under `assets/machines/<machine>/`, where `<machine>` is the
name in the `~/.dotfiles-machine` marker (`work`, or `mbp-2e32ef99` for the
personal laptop). The override replaces the whole file — formats like
aerospace's TOML have no include directive — and a machine with no override (or
no marker) links the shared asset, so one machine's override never changes
another machine's install. The same tree holds the machine's own Claude
commands, hooks and skills under `machines/<machine>/claude/`. A marker is
recognized only when `assets/machines/<machine>/` exists; an unrecognized
marker installs no machine assets at all.

`assets/zshrc` is symlinked to `~/.zshrc`, so any third-party installer run
from here must be told not to append to shell config (opencode's
`--no-modify-path`); put the `PATH` entry in the tracked `zshrc` instead.
