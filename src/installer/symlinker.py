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
