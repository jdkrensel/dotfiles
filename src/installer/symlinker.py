"""Symlink management module."""

import shutil
from pathlib import Path

from .printer import Printer
from .utils import get_home_dir


class SymlinkManager:
    """Handles creation and management of symlinks."""

    def __init__(self, printer: Printer, dotfiles_dir: Path):
        self.printer = printer
        self.dotfiles_dir = dotfiles_dir
        self.home_dir = get_home_dir()

    def create_symlink(self, source: Path, destination: Path, backup: bool = True) -> bool:
        """Create a symlink with robust backup and cleanup handling."""
        source = source.resolve()

        # 1. Source must exist
        if not source.exists():
            self.printer.print_error(f"Source file not found: {source}")
            return False

        # 2. Check if the symlink is already correct
        if destination.is_symlink():
            try:
                if destination.readlink() == source:
                    self.printer.print_success(f"Symlink for {destination.name} is already correct")
                    return True
            except OSError:
                pass  # Broken symlink — proceed to clean it up

        # 3. Handle any existing destination (file, dir, or broken/wrong symlink)
        if destination.exists() or destination.is_symlink():
            try:
                if backup:
                    backup_path = destination.with_name(destination.name + '.bak')
                    if backup_path.exists() or backup_path.is_symlink():
                        if backup_path.is_dir() and not backup_path.is_symlink():
                            shutil.rmtree(backup_path)
                        else:
                            backup_path.unlink()
                    destination.rename(backup_path)
                    self.printer.print_success(f"Created backup: {backup_path.name}")
                else:
                    if destination.is_dir() and not destination.is_symlink():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()
            except Exception as e:
                self.printer.print_error(f"Failed to clean up destination {destination.name}: {e}")
                self.printer.print_error("FATAL: Destination path is NOT clear. Check permissions or if file is locked.")
                return False

        # 4. Create the new symlink
        try:
            destination.symlink_to(source)
            self.printer.print_success(f"Created symlink for {destination.name}")
            return True
        except Exception as e:
            self.printer.print_error(f"Failed to create symlink for {destination.name}: {e}")
            if backup:
                backup_path = destination.with_name(destination.name + '.bak')
                if backup_path.exists():
                    self.printer.print_info(f"Attempting to restore backup from {backup_path.name}...")
                    backup_path.rename(destination)
            return False

    def _link(self, src_file: Path, dest_path: Path) -> bool:
        """Check if a symlink needs updating, prompt for backup if so, then create it."""
        if dest_path.is_symlink():
            try:
                if dest_path.readlink() == src_file.resolve():
                    self.printer.print_success(f"Symlink for {dest_path.name} is already correct")
                    return True
            except OSError:
                pass  # Broken symlink — proceed to recreate

        create_backup = True
        if dest_path.exists() or dest_path.is_symlink():
            try:
                answer = input(f"File {dest_path.name} exists. Create backup to {dest_path.name}.bak? (y/n): ").strip().lower()
                create_backup = answer in ('y', 'yes')
            except EOFError:
                self.printer.print_info("No input received, defaulting to creating a backup.")

        return self.create_symlink(src_file, dest_path, backup=create_backup)

    def setup_dotfiles_symlinks(self, files: list[str]) -> bool:
        """Set up symlinks for dotfiles in the home directory (e.g. zshrc → ~/.zshrc)."""
        self.printer.print_current_step("Creating symlinks for configuration files...")
        source_dir = self.dotfiles_dir / "src" / "assets"
        all_successful = True
        for file in files:
            if not self._link(source_dir / file, self.home_dir / f".{file}"):
                all_successful = False
        return all_successful

    def setup_config_symlinks(self, files: list[str]) -> bool:
        """Set up symlinks for files in ~/.config/."""
        self.printer.print_current_step("Creating symlinks for ~/.config files...")
        source_dir = self.dotfiles_dir / "src" / "assets" / "config"
        config_dir = self.home_dir / ".config"
        config_dir.mkdir(parents=True, exist_ok=True)
        all_successful = True
        for file in files:
            if not self._link(source_dir / file, config_dir / file):
                all_successful = False
        return all_successful

    def setup_home_symlinks(self, files: list[tuple[str, str]]) -> bool:
        """Set up symlinks for non-dot files in the home directory."""
        self.printer.print_current_step("Creating symlinks for home directory files...")
        source_dir = self.dotfiles_dir / "src" / "assets"
        all_successful = True
        for source_name, dest_name in files:
            if not self._link(source_dir / source_name, self.home_dir / dest_name):
                all_successful = False
        return all_successful

    def setup_home_subdir_symlinks(self, files: list[tuple[str, str]]) -> bool:
        """Set up symlinks in home subdirectories, creating parent dirs as needed."""
        self.printer.print_current_step("Creating symlinks for home subdirectory files...")
        source_dir = self.dotfiles_dir / "src" / "assets"
        all_successful = True
        for source_name, dest_relative in files:
            dest_path = self.home_dir / dest_relative
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._link(source_dir / source_name, dest_path):
                all_successful = False
        return all_successful

    # Maps a profile token (as written in a command's `profiles:` frontmatter, and
    # matching the clp/clb shell aliases) to that profile's root dir under $HOME.
    CLAUDE_PROFILES = {
        "clp": ".claude",          # default profile (~/.claude)
        "clb": ".claude-bedrock",  # Bedrock profile used for PHI work
    }

    @staticmethod
    def _allowed_profiles(command: Path) -> set[str]:
        """Return the profile tokens a local command opts into.

        A command may declare `profiles: clp, clb` in its YAML frontmatter to
        restrict which Claude profiles it installs into. The line is parsed
        textually (no YAML dependency); only tokens in CLAUDE_PROFILES are kept.
        Absent or empty → all known profiles, preserving the default of
        installing every command into every profile.
        """
        all_profiles = set(SymlinkManager.CLAUDE_PROFILES)
        lines = command.read_text().splitlines()
        if not lines or lines[0].strip() != "---":
            return all_profiles  # no frontmatter → default to every profile
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break  # end of frontmatter; `profiles:` only counts in the header
            if stripped.startswith("profiles:"):
                tokens = stripped.split(":", 1)[1].replace(",", " ").split()
                requested = {t for t in tokens if t in all_profiles}
                return requested or all_profiles
        return all_profiles

    def _require_machine_category(self) -> str | None:
        """Resolve this machine's category from the ~/.dotfiles-machine marker.

        Machine-scoped assets (local commands, local hooks) live under
        src/assets/claude/machines/<category>/ and are tracked in git —
        split by machine (e.g. work vs personal) rather than gitignored.
        The marker file names which category this machine is.

        Prints a clear, actionable error and returns None if the marker is
        missing or names a category with no matching machines/<category>/
        directory, rather than silently skipping: a fresh machine with no
        marker should fail loudly, not quietly end up with zero local
        commands/hooks and no indication why.
        """
        marker = self.home_dir / ".dotfiles-machine"
        machines_dir = self.dotfiles_dir / "src" / "assets" / "claude" / "machines"
        known = sorted(p.name for p in machines_dir.iterdir() if p.is_dir()) if machines_dir.is_dir() else []
        known_desc = ", ".join(known) if known else "(none defined yet)"

        if not marker.is_file():
            self.printer.print_error("\n".join([
                f"Machine category marker not found: {marker}",
                f"  Create it with this machine's category, e.g.: echo work > {marker}",
                f"  Known categories: {known_desc}",
            ]))
            return None

        category = marker.read_text().strip()
        if category not in known:
            self.printer.print_error("\n".join([
                f"Unrecognized machine category '{category}' in {marker}.",
                f"  Known categories: {known_desc}",
            ]))
            return None

        return category

    def _prune_stale_command(self, dest: Path, source: Path) -> None:
        """Remove a previously-installed link for a now-denied command.

        Only ever unlinks `dest` when it is a symlink resolving to `source` (our
        own command file) — never a real file or an unrelated symlink, so a
        deny can't clobber something the installer didn't create.
        """
        if dest.is_symlink():
            try:
                resolves_to_us = dest.readlink() == source or dest.resolve() == source.resolve()
            except OSError:
                resolves_to_us = False  # broken link — leave it for the user to inspect
            if resolves_to_us:
                dest.unlink()
                self.printer.print_info(f"Removed {dest.name} from {dest.parent.parent.name} (profile opted out)")

    def setup_local_commands(self) -> bool:
        """Symlink this machine's local Claude commands into each Claude profile's commands dir.

        Commands live in src/assets/claude/machines/<category>/commands/*.md,
        tracked in git and split by machine category (e.g. work vs personal) —
        see _require_machine_category(). On a recognized machine with no
        commands defined yet, this is a no-op — mirroring the optional
        ~/.zshrc.local pattern.

        By default each command is linked into every known Claude profile whose
        root dir exists on this machine: the default profile (~/.claude/) and the
        Bedrock profile (~/.claude-bedrock/) used for PHI work. A command can
        narrow this with a `profiles:` frontmatter line (e.g. `profiles: clb`) —
        an allow-list; omitting a profile denies it, and any stale link from a
        previous install is pruned. A profile dir that doesn't exist on this
        machine is skipped rather than created.
        """
        category = self._require_machine_category()
        if category is None:
            return False

        commands_dir = self.dotfiles_dir / "src" / "assets" / "claude" / "machines" / category / "commands"
        commands = sorted(commands_dir.glob("*.md")) if commands_dir.is_dir() else []
        if not commands:
            return True

        self.printer.print_current_step("Creating symlinks for machine-local Claude commands...")
        all_successful = True
        for token, root_name in self.CLAUDE_PROFILES.items():
            root = self.home_dir / root_name
            # The default profile is always set up; extra profiles only get links
            # if their root dir already exists on this machine.
            if token != "clp" and not root.is_dir():
                continue
            dest_dir = root / "commands"
            dest_dir.mkdir(parents=True, exist_ok=True)
            for src_file in commands:
                dest = dest_dir / src_file.name
                if token in self._allowed_profiles(src_file):
                    if not self._link(src_file, dest):
                        all_successful = False
                else:
                    self._prune_stale_command(dest, src_file)
        return all_successful

    def setup_claude_rules(self) -> bool:
        """Symlink Claude rules into each Claude profile's rules dir.

        Path-scoped rule files in src/assets/claude/rules/*.md are injected by
        the harness when a matching file is in play. They install into every
        known Claude profile whose root dir exists on this machine: the default
        profile (~/.claude/) and the Bedrock profile (~/.claude-bedrock/) used
        for PHI work — so the same guidance applies whichever profile a file is
        edited in. A profile dir that doesn't exist on this machine is skipped
        rather than created, mirroring setup_local_commands.
        """
        rules_dir = self.dotfiles_dir / "src" / "assets" / "claude" / "rules"
        rules = sorted(rules_dir.glob("*.md")) if rules_dir.is_dir() else []
        if not rules:
            return True

        self.printer.print_current_step("Creating symlinks for Claude rules...")
        all_successful = True
        for token, root_name in self.CLAUDE_PROFILES.items():
            root = self.home_dir / root_name
            # The default profile is always set up; extra profiles only get links
            # if their root dir already exists on this machine.
            if token != "clp" and not root.is_dir():
                continue
            dest_dir = root / "rules"
            dest_dir.mkdir(parents=True, exist_ok=True)
            for src_file in rules:
                if not self._link(src_file, dest_dir / src_file.name):
                    all_successful = False
        return all_successful

    def setup_claude_hooks(self) -> bool:
        """Symlink Claude hook scripts into ~/.claude/hooks/.

        Shared, machine-agnostic hooks in src/assets/claude/hooks/* are always
        symlinked. Machine-scoped hooks in
        src/assets/claude/machines/<category>/hooks/* are tracked in git and
        split by machine category — see _require_machine_category(). Mirrors
        setup_local_commands.
        """
        category = self._require_machine_category()
        if category is None:
            return False

        hooks_dir = self.dotfiles_dir / "src" / "assets" / "claude" / "hooks"
        shared = sorted(p for p in hooks_dir.glob("*") if p.is_file())
        machine_dir = self.dotfiles_dir / "src" / "assets" / "claude" / "machines" / category / "hooks"
        machine = sorted(p for p in machine_dir.glob("*") if p.is_file()) if machine_dir.is_dir() else []
        scripts = shared + machine
        if not scripts:
            return True

        self.printer.print_current_step("Creating symlinks for Claude hooks...")
        dest_dir = self.home_dir / ".claude" / "hooks"
        dest_dir.mkdir(parents=True, exist_ok=True)
        all_successful = True
        for src_file in scripts:
            if not self._link(src_file, dest_dir / src_file.name):
                all_successful = False
        return all_successful

    def setup_git_log_script(self) -> bool:
        """Set up the git-log-hyperlinks script in ~/bin/."""
        self.printer.print_current_step("Setting up git-log-hyperlinks script...")

        bin_dir = self.home_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        script_src = self.dotfiles_dir / "src" / "scripts" / "git_log_hyperlinks.py"
        script_dest = bin_dir / "git_log_hyperlinks.py"

        if not script_src.exists():
            self.printer.print_error(f"Source script not found: {script_src}")
            return False

        if not self.create_symlink(script_src, script_dest, backup=True):
            return False

        try:
            script_dest.chmod(0o755)
            self.printer.print_success(f"Made {script_dest.name} executable")
        except Exception as e:
            self.printer.print_error(f"Could not make script executable: {e}")
            return False

        self.printer.print_success("Git alias 'lo' is configured in gitconfig to use ~/bin/git_log_hyperlinks.py")
        self.printer.print_info("You can now use 'git lo' to run the enhanced git log")
        return True
