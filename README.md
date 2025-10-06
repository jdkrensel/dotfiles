# Dotfiles

A modern dotfiles installer that sets up a comprehensive development environment on macOS, Linux, and WSL.

## Features

- **Modular Installer**: Robust installer with comprehensive error handling and type safety
- **Shell Configuration**: Enhanced zsh setup with autocompletion, syntax highlighting, custom aliases, and functions
- **Development Tools**: Curated package collection including `fzf`, `zellij`, `eza`, `bat`, `fd`, `lnav`, `ripgrep`, and `zoxide`
- **Git Integration**: Enhanced git log with clickable hyperlinks and streamlined aliases
- **Cross-Platform**: Works seamlessly on macOS, Linux, and WSL with automatic environment detection

## Quick Start

### Prerequisites
- macOS, Linux, or WSL
- zsh shell (installer will guide you if not present)
- Homebrew (installed automatically if needed)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/dotfiles.git
cd dotfiles

# Run the installer
python3 -m src.installer
```

### Installing zsh (if needed)

**WSL/Linux:**
```bash
sudo apt update && sudo apt install -y zsh
chsh -s $(which zsh) && exec zsh -c 'python3 -m src.installer'
```

**macOS:** zsh is the default shell since macOS Catalina (10.15)

## Installer Features

The installer provides:

- **Modular Architecture**: Clean separation of concerns with dedicated modules for symlinks, system dependencies, and utilities
- **Robust Error Handling**: Comprehensive error checking with detailed diagnostics, recovery suggestions, and automatic backup restoration
- **Smart Interactions**: Intelligent handling of existing files with user-friendly backup options and robust symlink management
- **Environment Management**: Automatic setup of Homebrew, Rust, and Node.js environments
- **Cross-Platform**: Seamless operation on macOS, Linux, and WSL with automatic platform detection
- **Git Integration**: Advanced git log script with clickable hyperlinks for multiple VCS platforms

## Project Structure

```
dotfiles/
├── pyproject.toml                # Package configuration
├── .gitignore                    # Git ignore rules
├── README.md                     # Project documentation
├── bin/                          # Pre-built binaries (zellij)
└── src/                          # Source files
    ├── assets/                   # Dotfiles to be symlinked
    │   ├── zshrc                 # Main zsh configuration
    │   ├── aliases               # Custom shell aliases
    │   ├── functions             # Utility functions
    │   ├── gitconfig             # Git configuration
    │   ├── vimrc                 # Vim configuration
    │   └── Brewfile              # Homebrew packages
    ├── scripts/                  # Utility scripts
    │   └── git_log_hyperlinks.py # Enhanced git log with hyperlinks
    ├── installer/                # Installer package
    │   ├── __init__.py           # Package initialization
    │   ├── __main__.py           # Module entry point
    │   ├── installer.py          # Main installer logic
    │   ├── symlinker.py          # Symlink management
    │   ├── printer.py            # Terminal output formatting
    │   ├── constants.py          # Color constants
    │   └── utils/                # Utility modules
    │       ├── __init__.py       # Utils package init
    │       ├── shell.py          # Shell utilities
    │       ├── system.py         # System utilities
    │       └── process.py        # Process utilities
    └── doc/
        └── themes_and_fonts.md   # Theme and font recommendations
```

## What Gets Installed

### Homebrew Packages
- `bat` - Enhanced cat with syntax highlighting and git integration
- `eza` - Modern ls replacement with icons and git status
- `fd` - Fast, user-friendly find alternative
- `fzf` - Fuzzy finder with vim-like key bindings
- `lnav` - Advanced log file navigator
- `nvm` - Node.js version manager
- `ripgrep` - Ultra-fast text search tool
- `starship` - Cross-shell prompt with git integration
- `vivid` - LS_COLORS generator for better file type colors
- `zoxide` - Smart cd command that learns your habits
- `zsh-autosuggestions` - Fish-like autosuggestions for zsh
- `zsh-syntax-highlighting` - Real-time syntax highlighting

### Pre-built Binaries
- `zellij` - Terminal multiplexer (pre-compiled, ready to use)

### Shell Enhancements
- Custom aliases for git, navigation, and system operations
- Fish-like autosuggestions with zsh-autosuggestions
- Real-time command highlighting with zsh-syntax-highlighting
- Starship prompt with git status and directory info
- FZF integration for file and command history search
- Multiple startup themes (Slytherin, Matrix, Azure, Golden Hour)

### Git Integration
- Enhanced git log with `git lo` command and clickable hyperlinks
  - Multi-platform support: GitHub, Bitbucket, GitLab, and Azure DevOps
  - Clickable commit hashes in modern terminals
  - Clean, readable formatting with syntax highlighting
  - Graceful handling of non-git directories
  - Modern implementation for better maintainability

## Customization

### Startup Themes
- Slytherin Dungeon (default) - Dark green with mystical vibes
- Matrix Green - Classic terminal hacker aesthetic
- Azure Serenity - Clean blue tones for productivity
- Golden Hour - Warm, sunset-inspired colors

### Terminal Setup
- Recommended themes: See `doc/themes_and_fonts.md` for detailed recommendations
- Fonts: Nerd Fonts recommended for icon support
- Cursor: Block cursor recommended for better visibility