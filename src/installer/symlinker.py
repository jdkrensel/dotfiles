"""
Symlink management module.
"""

import os
import shutil
from pathlib import Path
from typing import List

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
                # This is a broken symlink, so we'll proceed to clean it up.
                pass

        # 3. Handle any existing destination (file, dir, or broken/wrong symlink)
        if destination.exists() or destination.is_symlink():
            try:
                if backup:
                    backup_path = destination.with_name(destination.name + '.bak')
                    # Clean up old backup if it exists
                    if backup_path.exists() or backup_path.is_symlink():
                        if backup_path.is_dir() and not backup_path.is_symlink():
                            shutil.rmtree(backup_path)
                        else:
                            backup_path.unlink()
                    destination.rename(backup_path)
                    self.printer.print_success(f"Created backup: {backup_path.name}")
                else:
                    # No backup, just remove the existing item
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
            # Attempt to restore backup if creation fails
            if backup:
                backup_path = destination.with_name(destination.name + '.bak')
                if backup_path.exists():
                    self.printer.print_info(f"Attempting to restore backup from {backup_path.name}...")
                    backup_path.rename(destination)
            return False

    def setup_dotfiles_symlinks(self, files_to_symlink: List[str]) -> bool:
        """Set up symlinks for dotfiles configuration files."""
        self.printer.print_current_step("Creating symlinks for configuration files...")
        
        source_dir = self.dotfiles_dir / "src" / "assets"
        all_successful = True

        for file in files_to_symlink:
            src_file = source_dir / file
            dest_path = self.home_dir / f".{file}"
            
            # This initial check is still good, as it avoids the user prompt.
            if dest_path.is_symlink():
                try:
                    if dest_path.readlink() == src_file.resolve():
                        self.printer.print_success(f"Symlink for {dest_path.name} is already correct")
                        continue # Skip to next file
                except OSError:
                    pass # Broken link, proceed.

            create_backup = True
            # THE FIX IS HERE: Use the corrected check before prompting the user.
            if dest_path.exists() or dest_path.is_symlink():
                try:
                    backup_choice = input(f"File {dest_path.name} exists. Create backup to {dest_path.name}.bak? (y/n): ").strip().lower()
                    create_backup = backup_choice in ['y', 'yes']
                except EOFError:
                    self.printer.print_warning("No input received, defaulting to creating a backup.")
                    create_backup = True


            # Rely on the robust, single method to do the work.
            if not self.create_symlink(src_file, dest_path, backup=create_backup):
                all_successful = False
                
        return all_successful

    def setup_config_symlinks(self, files_to_symlink: List[str]) -> bool:
        """Set up symlinks for ~/.config/ configuration files."""
        self.printer.print_current_step("Creating symlinks for ~/.config files...")

        source_dir = self.dotfiles_dir / "src" / "assets" / "config"
        config_dir = self.home_dir / ".config"

        # Create ~/.config if it doesn't exist
        if not config_dir.exists():
            config_dir.mkdir(parents=True)
            self.printer.print_success("Created ~/.config directory")

        all_successful = True

        for file in files_to_symlink:
            src_file = source_dir / file
            dest_path = config_dir / file

            if dest_path.is_symlink():
                try:
                    if dest_path.readlink() == src_file.resolve():
                        self.printer.print_success(f"Symlink for {dest_path.name} is already correct")
                        continue
                except OSError:
                    pass

            create_backup = True
            if dest_path.exists() or dest_path.is_symlink():
                try:
                    backup_choice = input(f"File {dest_path.name} exists. Create backup to {dest_path.name}.bak? (y/n): ").strip().lower()
                    create_backup = backup_choice in ['y', 'yes']
                except EOFError:
                    self.printer.print_warning("No input received, defaulting to creating a backup.")
                    create_backup = True

            if not self.create_symlink(src_file, dest_path, backup=create_backup):
                all_successful = False

        return all_successful

    def setup_git_log_script(self) -> bool:
        """Set up the git-log-hyperlinks script."""
        self.printer.print_current_step("Setting up git-log-hyperlinks script...")
        
        # Create ~/bin directory if it doesn't exist
        bin_dir = self.home_dir / "bin"
        if not bin_dir.exists():
            bin_dir.mkdir(parents=True)
            self.printer.print_success("Created ~/bin directory")
        
        script_src = self.dotfiles_dir / "src" / "scripts" / "git_log_hyperlinks.py"
        script_dest = bin_dir / "git_log_hyperlinks.py"
        
        if not script_src.exists():
            self.printer.print_error(f"Source script not found: {script_src}")
            return False
        
        # Use the corrected create_symlink method
        if not self.create_symlink(script_src, script_dest, backup=True):
            return False
        
        # Make the script executable
        try:
            script_dest.chmod(0o755)
            self.printer.print_success(f"Made {script_dest.name} executable")
        except Exception as e:
            self.printer.print_error(f"Could not make script executable: {e}")
            return False

        self.printer.print_success("Git alias 'lo' is configured in gitconfig to use ~/bin/git_log_hyperlinks.py")
        self.printer.print_info("You can now use 'git lo' to run the enhanced git log")
        return True
