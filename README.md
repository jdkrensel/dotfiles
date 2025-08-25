# 🚀 Dotfiles

A curated collection of configuration files and scripts to set up a modern development environment on macOS/Linux.

## ✨ Features

- **Shell Configuration**: Enhanced zsh setup with autocompletion, syntax highlighting, custom aliases, and custom functions
- **Development Tools**: Pre-configured set of packages including `fzf`, `zellij`, `eza`, `bat`, `fd`, `lnav`, `ripgrep`, and `zoxide`.
- **Git Integration**: Streamlined git aliases and configuration
- **Package Management**: Automated installation via installer script

## 🛠️ Quick Start

### Prerequisites
- macOS/Linux OS
- zsh shell

### Installing zsh (if not already installed)

**WSL/Linux:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y zsh

# Set zsh as default shell
chsh -s $(which zsh)
```

**Note:** After installing zsh, you may need to log out and back in for the shell change to take effect.

### Installation
```bash
chmod +x install.sh && ./install.sh
```

## 📁 Structure

```
dotfiles/
├── install.sh          # Automated installation script
├── bin/                # Pre-built binaries (zellij)
├── src/                # Source configuration files
│   ├── zshrc          # Main zsh configuration
│   ├── aliases        # Custom shell aliases
│   ├── functions      # Utility functions
│   ├── gitconfig      # Git configuration
│   ├── vimrc          # Vim configuration
│   ├── Brewfile       # Homebrew packages
│   └── home_row_mods.kbd  # Keyboard modifications
└── doc/
    └── themes_and_fonts.md  # Theme and font recommendations
```

## 🔧 What Gets Installed

### Homebrew Packages
- `bat` - Enhanced cat with syntax highlighting
- `eza` - Modern ls replacement
- `fd` - Fast finder
- `fzf` - Fuzzy finder
- `lnav` - Log navigator
- `nvm` - Node version manager
- `ripgrep` - Fast grep alternative
- `starship` - Cross-shell prompt
- `vivid` - LS_COLORS generator
- `zoxide` - Smart cd command
- `zsh-autosuggestions` - Fish-like autosuggestions
- `zsh-syntax-highlighting` - Syntax highlighting

### Pre-built Binaries
- `zellij` - Terminal multiplexer (ready to use, no compilation needed)

### Shell Enhancements
- Custom aliases for git, navigation, and safety
- Enhanced autocompletion with zsh-autosuggestions
- Syntax highlighting with zsh-syntax-highlighting
- Starship prompt
- FZF integration
- Custom startup banners with multiple themes

## 🎨 Customization

**Startup Themes**: Slytherin Dungeon (default), Matrix Green, Azure Serenity, Golden Hour  
**Optional**: Terminal themes, fonts, cursor preferences (see `doc/themes_and_fonts.md`)

