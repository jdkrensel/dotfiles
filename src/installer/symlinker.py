"""Symlink management module."""

import shutil
from pathlib import Path

from . import resolver
from .printer import Printer
from .utils import get_home_dir


class SymlinkManager:
    """Handles creation and management of symlinks."""

    def __init__(self, printer: Printer, dotfiles_dir: Path, dry_run: bool = False):
        self.printer = printer
        self.dotfiles_dir = dotfiles_dir
        self.home_dir = get_home_dir()
        self.dry_run = dry_run
        # Every destination this run has linked, so remove_broken_links can clean up
        # the same directories without a second list of them to keep in step.
        self.linked_dests: set[Path] = set()

    def _mkdir(self, directory: Path) -> None:
        """Create a destination directory, unless this is a dry run."""
        if not self.dry_run:
            directory.mkdir(parents=True, exist_ok=True)

    def create_symlink(self, source: Path, destination: Path, backup: bool = True) -> bool:
        """Create a symlink with robust backup and cleanup handling."""
        source = source.resolve()

        # 1. Source must exist
        if not source.exists():
            self.printer.print_error(f"Source file not found: {source}")
            return False

        # 2. On a dry run, report the outcome and stop before touching anything.
        # Every symlink the installer creates goes through here, so this one guard
        # covers the whole install rather than simulating it on a parallel path.
        if self.dry_run:
            status = resolver.link_status(resolver.Link(source=source, dest=destination, group=""))
            if status is resolver.LinkStatus.CURRENT:
                self.printer.print_success(f"Symlink for {destination.name} is already correct")
            else:
                self.printer.print_info(f"Would {status} {destination} -> {source}")
            return True

        # 3. Check if the symlink is already correct
        if destination.is_symlink():
            try:
                if destination.readlink() == source:
                    self.printer.print_success(f"Symlink for {destination.name} is already correct")
                    return True
            except OSError:
                pass  # Broken symlink — proceed to clean it up

        # 4. Handle any existing destination (file, dir, or broken/wrong symlink)
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

        # 5. Create the new symlink
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
        self.linked_dests.add(dest_path)

        # Checked before "already correct": a dangling link to a deleted source
        # still matches it, and would otherwise pass as current.
        if not src_file.exists():
            self.printer.print_error(f"Source file not found: {src_file}")
            return False

        if dest_path.is_symlink():
            try:
                if dest_path.readlink() == src_file.resolve():
                    self.printer.print_success(f"Symlink for {dest_path.name} is already correct")
                    return True
            except OSError:
                pass  # Broken symlink — proceed to recreate

        create_backup = True
        if not self.dry_run and (dest_path.exists() or dest_path.is_symlink()):
            try:
                answer = input(f"File {dest_path.name} exists. Create backup to {dest_path.name}.bak? (y/n): ").strip().lower()
                create_backup = answer in ('y', 'yes')
            except EOFError:
                self.printer.print_info("No input received, defaulting to creating a backup.")

        return self.create_symlink(src_file, dest_path, backup=create_backup)

    def setup_home_links(self) -> bool:
        """Symlink each file in resolver.HOME_LINKS to its fixed place under $HOME.

        A machine with no marker, or an unrecognized one, gets the shared files: an
        override is optional, so an unmarked machine still installs. Machine-scoped
        Claude assets are stricter and demand a marker (see _require_machine).
        """
        assets_dir = self.dotfiles_dir / "src" / "assets"
        machine = resolver.machine_name(self.home_dir, assets_dir)
        return self._apply(resolver.HOME_GROUP, "Creating symlinks for home files...", machine=machine)

    def _require_machine(self) -> str | None:
        """Resolve this machine's name from the ~/.dotfiles-machine marker.

        Machine-scoped assets (local commands, local hooks) live under
        src/assets/machines/<machine>/claude/ and are tracked in git —
        split by machine (work, or the personal laptop) rather than gitignored.
        The marker file names this machine.

        Prints a clear, actionable error and returns None if the marker is
        missing or names a machine with no matching machines/<machine>/
        directory, rather than silently skipping: a fresh machine with no
        marker should fail loudly, not quietly end up with zero local
        commands/hooks and no indication why.
        """
        assets_dir = self.dotfiles_dir / "src" / "assets"
        machine = resolver.machine_name(self.home_dir, assets_dir)
        if machine is not None:
            return machine

        # Recognized nothing — say which of the two reasons it was.
        marker = self.home_dir / ".dotfiles-machine"
        known = resolver.known_machines(assets_dir)
        known_desc = ", ".join(known) if known else "(none defined yet)"

        if not marker.is_file():
            self.printer.print_error("\n".join([
                f"Machine marker not found: {marker}",
                f"  Create it with this machine's name, e.g.: echo work > {marker}",
                f"  Known machines: {known_desc}",
            ]))
            return None

        self.printer.print_error("\n".join([
            f"Unrecognized machine '{marker.read_text().strip()}' in {marker}.",
            f"  Known machines: {known_desc}",
        ]))
        return None

    def _prune_stale_link(self, dest: Path, source: Path) -> None:
        """Remove a previously-installed link for a now-denied asset.

        Only ever unlinks `dest` when it is a symlink resolving to `source` (our own
        command file or skill directory) — never a real file or directory, and never
        an unrelated symlink, so a deny can't clobber something the installer didn't
        create. Unlinking a symlink-to-directory removes just the link, leaving the
        skill's bundled contents intact.
        """
        prune = resolver.Prune(source=source, dest=dest, group="")
        if resolver.prune_status(prune) is not resolver.PruneStatus.REMOVE:
            return
        if self.dry_run:
            self.printer.print_info(f"Would remove {dest} (profile opted out)")
            return
        dest.unlink()
        self.printer.print_info(f"Removed {dest.name} from {dest.parent.parent.name} (profile opted out)")

    def _plan(self, group: str, machine: str | None = None) -> resolver.Plan:
        """Resolve one install step against the profiles active on this machine."""
        return resolver.resolve(
            assets_dir=self.dotfiles_dir / "src" / "assets",
            home_dir=self.home_dir,
            profiles=resolver.active_profiles(self.home_dir),
            machine=machine,
            group=group,
        )

    def _execute(self, plan: resolver.Plan) -> bool:
        """Carry out a resolved plan: prune opted-out links, then create the rest."""
        all_successful = True
        for prune in plan.prunes:
            self._prune_stale_link(prune.dest, prune.source)
        for link in plan.links:
            self._mkdir(link.dest.parent)
            if not self._link(link.source, link.dest):
                all_successful = False
        return all_successful

    def _apply(self, group: str, step: str, machine: str | None = None) -> bool:
        """Resolve and execute one install step, announcing it only if it does work.

        A malformed `profiles:` allow-list fails the step with a readable message
        rather than a traceback: resolving refuses to guess, because the guess would
        install a narrowed asset into every profile. Since the caller stops at the
        first failed step, that aborts the whole install — deliberate, as the fix is a
        one-line frontmatter correction and a re-run is idempotent.

        An empty plan is a legitimate no-op: a collection with nothing tracked in it
        yet — a recognized machine with no local commands, say — creates no
        directories and prints no step header.
        """
        try:
            plan = self._plan(group, machine)
        except ValueError as error:
            self.printer.print_error(str(error))
            return False
        if plan.is_empty:
            return True
        self.printer.print_current_step(step)
        return self._execute(plan)

    def setup_local_commands(self) -> bool:
        """Symlink this machine's local Claude commands into each profile's commands dir.

        Narrowable: a `profiles:` frontmatter line restricts a command to a subset of
        profiles, and any link left behind by a previous install is pruned. See
        resolver.COLLECTIONS for the routing rules.
        """
        machine = self._require_machine()
        if machine is None:
            return False
        return self._apply(
            "local-commands",
            "Creating symlinks for machine-local Claude commands...",
            machine=machine,
        )

    def setup_local_skills(self) -> bool:
        """Symlink this machine's local Claude skills into each profile's skills dir.

        Each skill is a directory holding SKILL.md plus any bundled resources, and is
        linked whole so those bundled files travel with it. Narrowable: a `profiles:`
        line in the skill's SKILL.md restricts it to a subset of profiles, so a skill
        that touches PHI or production can stay Bedrock-only.
        """
        machine = self._require_machine()
        if machine is None:
            return False
        return self._apply(
            "local-skills",
            "Creating symlinks for machine-local Claude skills...",
            machine=machine,
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

    def setup_claude_skills(self) -> bool:
        """Symlink shared Claude skills into each profile's skills dir.

        Each skill directory is linked whole, as in setup_local_skills, but fans out
        to every existing profile with no `profiles:` narrowing.
        """
        return self._apply("skills", "Creating symlinks for shared Claude skills...")

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
        machine = self._require_machine()
        if machine is None:
            return False
        return self._apply("hooks", "Creating symlinks for Claude hooks...", machine=machine)

    def remove_broken_links(self) -> bool:
        """Remove links into this repo whose targets no longer exist.

        Deleting or renaming an asset leaves its old link dangling on every machine
        that installed it. This removes those links from every directory this run
        linked into, plus each profile's collection directories, which may have
        nothing left to link once their last asset is gone. Run it after the other
        steps so ``linked_dests`` is complete.

        Only links that point into the repo are touched — see
        resolver.broken_repo_links. A destination this run linked is skipped: a real
        run has already replaced it, and a dry run only reports that replacement, so
        both report the same work. Announces itself only when there is work to do.
        """
        directories = {dest.parent for dest in self.linked_dests}
        for profile in resolver.active_profiles(self.home_dir):
            for collection in resolver.COLLECTIONS:
                directories.add(profile.root / collection.into if collection.into else profile.root)

        found = resolver.broken_repo_links(directories, self.dotfiles_dir)
        broken = [link for link in found if link not in self.linked_dests]
        if not broken:
            return True

        self.printer.print_current_step("Removing broken links into the repo...")
        all_successful = True
        for link in broken:
            if self.dry_run:
                self.printer.print_info(f"Would remove {link} (target no longer exists)")
                continue
            try:
                link.unlink()
            except OSError as error:
                self.printer.print_error(f"Failed to remove {link}: {error}")
                all_successful = False
                continue
            self.printer.print_info(f"Removed {link} (target no longer exists)")
        return all_successful
