"""Symlink management module."""

import shutil
from pathlib import Path

from . import resolver
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

    def _plan(self, group: str, machine: str | None = None) -> resolver.Plan:
        """Resolve one install step against the profiles active on this machine."""
        return resolver.resolve(
            assets_dir=self.dotfiles_dir / "src" / "assets",
            profiles=resolver.active_profiles(self.home_dir),
            machine=machine,
            group=group,
        )

    def _execute(self, plan: resolver.Plan) -> bool:
        """Carry out a resolved plan: prune opted-out links, then create the rest."""
        all_successful = True
        for prune in plan.prunes:
            self._prune_stale_command(prune.dest, prune.source)
        for link in plan.links:
            link.dest.parent.mkdir(parents=True, exist_ok=True)
            if not self._link(link.source, link.dest):
                all_successful = False
        return all_successful

    def _apply(self, group: str, step: str, machine: str | None = None) -> bool:
        """Resolve and execute one install step, announcing it only if it does work.

        An empty plan is a legitimate no-op: a collection with nothing tracked in it
        yet — a recognized machine with no local commands, say — creates no
        directories and prints no step header.
        """
        plan = self._plan(group, machine)
        if plan.is_empty:
            return True
        self.printer.print_current_step(step)
        return self._execute(plan)

    def setup_local_commands(self) -> bool:
        """Symlink this machine's local Claude commands into each profile's commands dir.

        The only narrowable collection: a `profiles:` frontmatter line restricts a
        command to a subset of profiles, and any link left behind by a previous
        install is pruned. See resolver.COLLECTIONS for the routing rules.
        """
        category = self._require_machine_category()
        if category is None:
            return False
        return self._apply(
            "local-commands",
            "Creating symlinks for machine-local Claude commands...",
            machine=category,
        )

    def setup_local_skills(self) -> bool:
        """Symlink this machine's local Claude skills into each profile's skills dir.

        Each skill is a directory holding SKILL.md plus any bundled resources, and is
        linked whole so those bundled files travel with it.
        """
        category = self._require_machine_category()
        if category is None:
            return False
        return self._apply(
            "local-skills",
            "Creating symlinks for machine-local Claude skills...",
            machine=category,
        )

    def setup_claude_rules(self) -> bool:
        """Symlink path-scoped Claude rules into each profile's rules dir."""
        return self._apply("rules", "Creating symlinks for Claude rules...")

    def setup_claude_agents(self) -> bool:
        """Symlink custom Claude subagents into each profile's agents dir."""
        return self._apply("agents", "Creating symlinks for Claude agents...")

    def setup_claude_commands(self) -> bool:
        """Symlink shared Claude slash-commands into each profile's commands dir.

        Unlike setup_local_commands these are deliberately not narrowable — fanning
        out to every existing profile is the whole point of a shared command.
        """
        return self._apply("commands", "Creating symlinks for shared Claude commands...")

    def setup_claude_statusline(self) -> bool:
        """Symlink the shared status line script into each Claude profile's root.

        The statusLine command in the shared settings fragment resolves the profile
        root at runtime via $CLAUDE_CONFIG_DIR (set by the clb alias), falling back
        to ~/.claude.
        """
        src_file = self.dotfiles_dir / "src" / "assets" / "claude" / "statusline.sh"
        if not src_file.is_file():
            # Unlike the rules/agents collections, this is a single required asset:
            # the shared settings fragment points every profile at it, so a missing
            # script means a broken status bar, not a legitimately-empty set.
            self.printer.print_error(f"Status line script not found: {src_file}")
            return False

        return self._apply("statusline", "Creating symlinks for the Claude status line...")

    def setup_claude_hooks(self) -> bool:
        """Symlink shared and machine-scoped Claude hook scripts into ~/.claude/hooks/.

        Hooks are pinned to the default profile: they are registered by path in that
        profile's settings.json, so a copy under another profile root would never
        be read.
        """
        category = self._require_machine_category()
        if category is None:
            return False
        return self._apply("hooks", "Creating symlinks for Claude hooks...", machine=category)

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
