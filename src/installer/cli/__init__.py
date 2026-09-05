"""Read-only commands that report on the installer's decisions.

Each module here is one command, named for the verb it implements, and does
nothing but render :mod:`src.installer.resolver` output. Keeping them free of
filesystem writes is what makes them safe to run at any time — and keeps them
honest, since they answer using the same resolution the installer acts on.
"""

# `Context.load` is annotated with its own class, which is only lazily evaluated
# from 3.14 on. Importing this package must not depend on that: the README
# bootstraps the installer with whatever `python3` the machine already has.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import resolver
from ..printer import Printer
from ..resolver import Plan, Profile
from ..utils import get_dotfiles_dir, get_home_dir


@dataclass(frozen=True)
class Context:
    """What every command needs to know about the machine it is reporting on."""

    printer: Printer
    dotfiles_dir: Path
    home_dir: Path
    profiles: list[Profile]
    machine: str | None

    @classmethod
    def load(cls) -> Context:
        home_dir = get_home_dir()
        dotfiles_dir = get_dotfiles_dir()
        return cls(
            printer=Printer(),
            dotfiles_dir=dotfiles_dir,
            home_dir=home_dir,
            profiles=resolver.active_profiles(home_dir),
            machine=resolver.machine_category(home_dir, dotfiles_dir / "src" / "assets"),
        )

    @property
    def assets_dir(self) -> Path:
        return self.dotfiles_dir / "src" / "assets"

    def plan(self, group: str | None = None) -> Plan:
        """Resolve the whole tree (or one group) exactly as an install would."""
        return resolver.resolve(
            assets_dir=self.assets_dir,
            profiles=self.profiles,
            machine=self.machine,
            group=group,
        )

    def warn_if_no_machine(self) -> None:
        """Note that machine-scoped assets are missing from the report, and why.

        A command still reports on everything shared rather than failing, so an
        unconfigured machine can see what it *would* get.
        """
        if self.machine is not None:
            return
        known = resolver.known_machines(self.assets_dir)
        known_desc = ", ".join(known) if known else "(none defined yet)"
        self.printer.print_warning(
            f"No machine category set, so machine-scoped assets are omitted. "
            f"Set one with: echo <category> > {self.home_dir / '.dotfiles-machine'}  "
            f"[known: {known_desc}]"
        )

    def display(self, path: Path) -> str:
        """Shorten a path for a table cell: repo-relative, or ~-relative under $HOME.

        Each root is tried both as-is and resolved, since either may sit behind a
        symlink. ``path`` itself is never resolved: a link's own location is what
        the reader needs to see, not the repo file it points at.
        """
        for root, prefix in ((self.dotfiles_dir, ""), (self.home_dir, "~/")):
            for candidate in (root, root.resolve()):
                if path.is_relative_to(candidate):
                    return f"{prefix}{path.relative_to(candidate)}"
        return str(path)
