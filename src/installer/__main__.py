#!/usr/bin/env python3
"""
Dotfiles Installer Application Entry Point

Contains the main execution logic for the installer package.
Launch with: python3 -m src.installer

Argument parsing uses argparse rather than the Click that rules/python.md calls
for: this package declares no runtime dependencies, so that nothing has to be
installed before the installer can run. Depending on Click would mean the entry
point could not start until a package manager had already set up an environment
for it — which is part of what it exists to do.
"""
import argparse
import logging
import sys

from .cli import Context, doctor, plan, resolve
from .installer import DotfilesInstaller
from .printer import Printer
from .resolver import COLLECTIONS

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI. With no subcommand, the installer runs — as it always has."""
    parser = argparse.ArgumentParser(prog="python3 -m src.installer", description="Dotfiles installer.")
    parser.add_argument("--dry-run", action="store_true", help="report what an install would change, writing nothing")
    subcommands = parser.add_subparsers(dest="command")

    install = subcommands.add_parser("install", help="install dotfiles (the default with no subcommand)")
    # SUPPRESS so an unused subcommand flag doesn't overwrite the top-level one,
    # which would make `--dry-run install` silently perform a real install.
    install.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="report what would change without writing anything",
    )

    for name, help_text in (
        ("resolve", "show which tracked asset goes into which Claude profile"),
        ("plan", "show what an install would change, without changing anything"),
    ):
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument(
            "--group",
            choices=sorted({collection.group for collection in COLLECTIONS}),
            help="limit to one collection",
        )

    subcommands.add_parser("doctor", help="report drift an install would not fix on its own")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch a subcommand, defaulting to a full install.

    Returns:
        int: The process exit code (0 for success, non-zero for failure).
    """
    args = build_parser().parse_args(argv)
    try:
        if args.command in ("resolve", "plan", "doctor"):
            return _run_command(args)
        return 0 if DotfilesInstaller(dry_run=args.dry_run).run() else 1
    except Exception:
        logger.exception("An unhandled error occurred.")
        return 1


def _run_command(args: argparse.Namespace) -> int:
    """Run one read-only command, reporting a bad allow-list the way an install does.

    The ValueError catch is deliberately scoped to these three and not to the install
    path: ``SymlinkManager._apply`` already handles the frontmatter error per step, so
    any ValueError surfacing from an install is unexpected and has earned its traceback.
    """
    context = Context.load()
    try:
        if args.command == "resolve":
            return resolve.run(context, args.group)
        if args.command == "plan":
            return plan.run(context, args.group)
        return doctor.run(context)
    except ValueError as error:
        # A malformed `profiles:` allow-list. Resolving refuses to guess rather than
        # widening an asset's reach, so report it instead of letting a traceback through.
        Printer().print_error(str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
