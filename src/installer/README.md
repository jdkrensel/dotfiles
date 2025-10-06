# Dotfiles Installer Package

A Python package for installing and configuring dotfiles with support for multiple platforms and package managers.

## Features

- **Cross-platform support**: macOS, WSL, and Linux
- **Prerequisites installation**: Homebrew, Rust, nvm
- **Configuration management**: Automatic symlinking of dotfiles
- **Git integration**: Automatic git alias setup
- **Modular design**: Easy to extend and maintain
- **Zero dependencies**: Uses only Python standard library
- **Portable**: Can be installed anywhere Python is available

## Structure

```
src/install/
├── __init__.py          # Package initialization
├── installer.py         # Main installer class
├── prerequisites.py     # Prerequisites installation
├── symlinks.py         # Symlink management
├── utils.py            # Utility functions and classes
└── README.md           # This file
```

## Usage

### From the dotfiles directory:

```bash
# Run the Python installer
python3 install.py

# Or run directly
python3 -m src.install.installer
```


## Architecture

The installer is organized into several modules:

- **`DotfilesInstaller`**: Main orchestrator class
- **`PrerequisitesInstaller`**: Handles installation of system dependencies
- **`SymlinkManager`**: Manages configuration file symlinks
- **`Printer`**: Handles formatted terminal output
- **`Colors`**: ANSI color codes for terminal output