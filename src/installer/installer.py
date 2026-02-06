"""
Main installer class that orchestrates the entire installation process.
"""

import os
from pathlib import Path

from .printer import Printer
from .symlinker import SymlinkManager
from .utils import get_dotfiles_dir, get_home_dir, get_parent_process_name, command_exists, run_command, is_wsl, is_linux


class SystemDependencyManager:
    """Handles installation of system dependencies like Homebrew and Rust."""
    
    def __init__(self, printer: Printer):
        self.printer = printer
    
    def install_homebrew(self) -> bool:
        """Install Homebrew if not already installed."""
        if command_exists("brew"):
            self.printer.print_success("Homebrew is already installed")
            return self.setup_homebrew_environment()
        
        self.printer.print_info("Homebrew not found. Installing Homebrew...")
        
        # Install build-essential on WSL/Linux for Homebrew compilation
        if is_linux() or is_wsl():
            if command_exists("apt-get"):
                self.printer.print_info("Installing build-essential for Homebrew compilation...")
                run_command("sudo apt-get update")
                run_command("sudo apt-get install -y build-essential")
                self.printer.print_success("build-essential installed")
        
        # Install Homebrew
        run_command("/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        
        # Set up Homebrew environment variables
        return self.setup_homebrew_environment()
    
    def setup_homebrew_environment(self) -> bool:
        """Set up Homebrew environment variables for different platforms."""
        homebrew_paths = [
            ("/opt/homebrew/bin/brew", "/opt/homebrew/bin"),  # macOS Apple Silicon
            ("/usr/local/bin/brew", "/usr/local/bin"),        # macOS Intel
            ("/home/linuxbrew/.linuxbrew/bin/brew", "/home/linuxbrew/.linuxbrew/bin")  # Linux
        ]
        
        for brew_path, brew_bin in homebrew_paths:
            if Path(brew_path).exists():
                self.printer.print_info("Setting up Homebrew environment variables...")
                # Add to PATH for current session
                current_path = os.environ.get("PATH", "")
                os.environ["PATH"] = f"{brew_bin}:{current_path}"
                self.printer.print_success("Homebrew environment configured")
                return True
        
        self.printer.print_error("Homebrew installation path not found. Please restart your terminal and run the script again.")
        return False
    
    def install_uv(self) -> bool:
        """Install uv if not already installed."""
        if command_exists("uv"):
            self.printer.print_success("uv is already installed")
            return True

        self.printer.print_info("uv not found. Installing uv...")

        try:
            run_command("curl -LsSf https://astral.sh/uv/install.sh | sh")
            self.printer.print_success("uv installed successfully")
            return True
        except Exception as e:
            self.printer.print_error(f"Failed to install uv: {e}")
            return False

    def install_claude(self) -> bool:
        """Install Claude Code if not already installed."""
        if command_exists("claude"):
            self.printer.print_success("Claude Code is already installed")
            return True

        self.printer.print_info("Claude Code not found. Installing Claude Code...")

        try:
            run_command("curl -fsSL https://claude.ai/install.sh | bash")
            self.printer.print_success("Claude Code installed successfully")
            return True
        except Exception as e:
            self.printer.print_error(f"Failed to install Claude Code: {e}")
            return False
    
    def install_rust(self) -> bool:
        """Install Rust if not already installed."""
        if command_exists("cargo"):
            self.printer.print_success("Rust is already installed")
            return True
        
        self.printer.print_info("Rust not found. Installing Rust via rustup...")
        run_command("curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y")
        
        # Set up Rust environment
        cargo_env = Path.home() / ".cargo" / "env"
        if cargo_env.exists():
            # Read the cargo environment file and apply to current session
            with open(cargo_env, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('export PATH='):
                        # Extract PATH value and add to current PATH
                        path_value = line.split('=', 1)[1].strip('"\'')
                        current_path = os.environ.get("PATH", "")
                        os.environ["PATH"] = f"{path_value}:{current_path}"
                    elif line.startswith('export '):
                        # Handle other environment variables
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            key, value = parts
                            value = value.strip('"\'')
                            os.environ[key.replace('export ', '')] = value
        
        self.printer.print_success("Rust installed successfully")
        return True
      
    def install_homebrew_packages(self, brewfile_path: Path) -> bool:
        """Install packages from Brewfile."""
        if not brewfile_path.exists():
            self.printer.print_error(f"Brewfile not found at {brewfile_path}")
            return False
        
        self.printer.print_info("Installing packages from Brewfile...")
        run_command(f"brew bundle --file={brewfile_path}", check=False, capture_output=False)
        self.printer.print_success("Homebrew packages installed successfully")
        return True
    
    def install_system_dependencies(self) -> bool:
        """Install all system dependencies."""
        self.printer.print_section_header("Installing System Dependencies")

        # Install Homebrew
        if not self.install_homebrew():
            return False

        # Install Rust
        if not self.install_rust():
            return False

        # Install uv
        if not self.install_uv():
            return False

        # Install Claude Code
        if not self.install_claude():
            return False

        return True


class DotfilesInstaller:
    """Main installer class for dotfiles setup."""
    
    def __init__(self):
        self.printer = Printer()
        self.dotfiles_dir = get_dotfiles_dir()
        self.home_dir = get_home_dir()
        self.system_deps = SystemDependencyManager(self.printer)
        self.symlinks = SymlinkManager(self.printer, self.dotfiles_dir)
        
    
    def is_zsh(self) -> bool:
        """Check if zsh is available and change shell if needed."""
        if "zsh" in get_parent_process_name().lower():
            return True

        if not command_exists("zsh"):
            self.printer.print_error("zsh is not installed. Please install zsh first.")
            return False

        self.printer.print_info("This installer requires zsh to run properly.")
        self.printer.print_info("Please run the following command to change your shell to zsh and continue:")
        self.printer.print_info("chsh -s /bin/zsh && exec zsh -c 'python3 install.py'")

        return False
    
    def install_homebrew_packages(self) -> bool:
        """Install packages from Brewfile."""
        self.printer.print_section_header("Installing Homebrew Packages")
        
        brewfile_path = self.dotfiles_dir / "src" / "assets" / "Brewfile"
        return self.system_deps.install_homebrew_packages(brewfile_path)
    
    def setup_configuration_files(self) -> bool:
        """Set up configuration files and symlinks."""
        self.printer.print_section_header("Setting Up Configuration Files")
        
        # Set up dotfiles symlinks
        files_to_symlink = ["zshrc", "gitconfig", "vimrc"]
        if not self.symlinks.setup_dotfiles_symlinks(files_to_symlink):
            return False

        # Set up agent instructions in their expected locations
        agent_files = [
            ("AGENTS.md", ".codex/AGENTS.md"),
            ("AGENTS.md", ".claude/CLAUDE.md"),
            ("asana-skill.md", ".claude/skills/asana.md"),
            ("claude/commands/commit.md", ".claude/commands/commit.md"),
            ("claude/commands/optimize-query.md", ".claude/commands/optimize-query.md"),
            ("claude/settings.json", ".claude/settings.json"),
        ]
        if not self.symlinks.setup_home_subdir_symlinks(agent_files):
            return False

        # Set up ~/.config symlinks
        config_files = ["starship.toml"]
        if not self.symlinks.setup_config_symlinks(config_files):
            return False

        # Set up git-log-hyperlinks script
        if not self.symlinks.setup_git_log_script():
            return False
        
        return True
    
    def complete_installation(self) -> bool:
        """Complete the installation process."""
        self.printer.print_section_header("Installation Complete")
        self.printer.print_success("🎉 Installation complete! 🎉")
        
        self.printer.print_current_step("Reloading shell to apply all changes...")
        # Note: This would need to be handled by the shell script wrapper
        os.execv("/bin/zsh", ["zsh"])
        return True
    
    def run(self) -> bool:
        """Run the complete installation process."""
        self.printer.print_welcome_banner()
        
        # Check zsh requirement
        if not self.is_zsh():
            return False

        # Install system dependencies
        if not self.system_deps.install_system_dependencies():
            return False
        
        # Install Homebrew packages
        if not self.install_homebrew_packages():
            return False
        
        # Set up configuration files
        if not self.setup_configuration_files():
            return False

        # Complete installation
        if not self.complete_installation():
            return False
        
        return True
