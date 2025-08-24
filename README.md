# 🚀 Dotfiles

A curated collection of configuration files and scripts to set up a modern, productive development environment on macOS/Linux.

## ✨ Features

- **Shell Configuration**: Enhanced zsh setup with autocompletion, syntax highlighting, and custom aliases
- **Development Tools**: Pre-configured Homebrew packages including `bat`, `eza`, `fzf`, `ripgrep`, and `zoxide`
- **Git Integration**: Streamlined git aliases and configuration
- **Custom Functions**: Utility functions for common development tasks
- **Themed Terminal**: Multiple color themes with customizable startup banners
- **Package Management**: Automated installation via Homebrew and Rust

## 🛠️ Quick Start

### Prerequisites
- macOS or Linux with WSL2
- zsh shell
- Git

### Installation

1. **Make the installer executable**:
   ```bash
   chmod +x install.sh
   ```

2. **Run the installer**:
   ```bash
   ./install.sh
   ```
   The installer will prompt for your first name to customize the terminal banner.

3. **Restart your shell session** or run:
   ```bash
   source ~/.zshrc
   ```

## 📁 Structure

```
dotfiles/
├── install.sh          # Automated installation script
├── src/
│   ├── zshrc          # Main zsh configuration
│   ├── aliases        # Custom shell aliases
│   ├── functions      # Utility functions
│   ├── gitconfig      # Git configuration
│   ├── Brewfile       # Homebrew packages
│   └── home_row_mods.kbd  # Keyboard modifications
└── doc/
    └── themes_and_fonts.md  # Theme and font recommendations
```

## 🔧 What Gets Installed

### Homebrew Packages
- `bat` - Enhanced cat with syntax highlighting
- `eza` - Modern ls replacement
- `fzf` - Fuzzy finder
- `nvm` - Node version manager
- `ripgrep` - Fast grep alternative
- `zoxide` - Smart cd command

### Shell Enhancements
- Custom aliases for git, navigation, and safety
- Enhanced autocompletion
- Starship prompt
- FZF integration
- Custom startup banners with multiple themes

## 🎨 Customization

### Terminal Themes
Choose from several pre-built themes in your `.zshrc`:
- Slytherin Dungeon (default)
- Matrix Green
- Azure Serenity
- Golden Hour

### Fonts
Recommended: **FiraCode Nerd Font Mono** (size 11, weight Medium)

## 🚨 Manual Setup Required

After installation, you'll need to manually configure:
- Terminal emulator themes (see `doc/themes_and_fonts.md`)
- Font installation
- Cursor style preferences

## 🤝 Contributing

Feel free to submit issues and enhancement requests!
