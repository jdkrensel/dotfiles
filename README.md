# Dotfiles

A modern dotfiles installer that sets up a comprehensive development environment on macOS, Linux, and WSL.

## Quick Start

### Prerequisites
- macOS, Linux, or WSL
- zsh shell (installer will guide you if not present)
- Homebrew (installed automatically if needed)
- [uv](https://docs.astral.sh/uv/), which runs the installer on the Python 3.14 it requires:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Installation

```bash
# Clone the repository
git clone https://github.com/jdkrensel/dotfiles.git
cd dotfiles

# Run the installer
uv run -m src.installer
```

### Installing zsh (if needed)

**WSL/Linux:**
```bash
sudo apt update && sudo apt install -y zsh
chsh -s $(which zsh) && exec zsh -c 'uv run -m src.installer'
```

**macOS:** zsh is the default shell since macOS Catalina (10.15)

### Inspecting before installing

Three read-only commands report on what the installer would do. None of them
writes anything, and all three answer using the same resolution the installer
acts on, so they cannot disagree with it.

```bash
uv run -m src.installer resolve   # which tracked asset goes into which Claude profile
uv run -m src.installer plan      # what an install would change to the Claude assets
uv run -m src.installer doctor    # drift an install would not fix on its own
uv run -m src.installer --dry-run # walk the real install with every write suppressed
```

`resolve` and `plan` take `--group` to narrow to one collection (`rules`,
`agents`, `commands`, `skills`, `hooks`, `statusline`, `local-commands`, `local-skills`).
`doctor` exits non-zero when it finds something, so it can gate a script.

All three report on the Claude assets, which are the only thing resolved into a
plan. `--dry-run` is the one that covers a whole install — the shell files,
`~/.config`, `~/bin` and the `settings.json` merge included. It previews the
configuration phase only; the zsh check and the dependency phases (Homebrew,
Rust, uv, Claude Code, opencode) are skipped rather than simulated, since what
they would do depends on what their own package managers decide at run time.

## What Gets Installed

### System Tools
- `Claude Code` - Anthropic's official CLI for Claude AI
- `Homebrew` - Package manager for macOS and Linux
- `opencode` - Terminal coding agent, installed via its native installer so `opencode upgrade` works
- `Rust` - Systems programming language and toolchain
- `uv` - Fast Python package installer and resolver

### Homebrew Packages
- `bat` - Enhanced cat with syntax highlighting and git integration
- `eza` - Modern ls replacement with icons and git status
- `fd` - Fast, user-friendly find alternative
- `fzf` - Fuzzy finder with vim-like key bindings
- `lnav` - Advanced log file navigator
- `ripgrep` - Ultra-fast text search tool
- `starship` - Cross-shell prompt with git integration
- `vivid` - LS_COLORS generator for better file type colors
- `zoxide` - Smart cd command that learns your habits
- `zsh-autosuggestions` - Fish-like autosuggestions for zsh
- `zsh-syntax-highlighting` - Real-time syntax highlighting

### Cask Applications
- `ghostty` - GPU-accelerated terminal emulator

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

### Claude Skills
Shared skills in `src/assets/claude/skills/` are linked into every Claude profile on every machine.

- `anki-cards` - Reviews and drafts Anki flashcards, and adds approved cards through the AnkiMCP server. Reviewing and drafting work anywhere; adding cards needs the manual Anki setup below.

## Manual Setup

### Anki (for the `anki-cards` skill)
The installer doesn't do these steps. Do them once per machine where the skill should add cards to Anki.

1. Install Anki 26.9.3 or later from [apps.ankiweb.net](https://apps.ankiweb.net), sign in, and sync your collection.
2. Install the AnkiMCP add-on (Tools → Add-ons → Get Add-ons, code `124672614`), then restart Anki.
3. Register the MCP server with Claude Code (it's stored in the untracked `~/.claude.json`):
   ```bash
   claude mcp add anki -s user --transport http http://127.0.0.1:3141/
   ```
   A profile with its own config dir, such as `~/.claude-bedrock`, needs its own registration.
4. On macOS, turn off App Nap for Anki. Otherwise macOS can throttle Anki in the background and MCP requests time out:
   ```bash
   defaults write net.ankiweb.anki NSAppSleepDisabled -bool true
   ```
   To undo it: `defaults delete net.ankiweb.anki NSAppSleepDisabled`.

Anki must be open with a profile loaded when Claude Code starts, or the `mcp__anki__` tools won't connect. The deck and note type the skill uses are created in your collection on the first add, and AnkiWeb sync carries them to other machines.

## Customization

### Startup Themes
- Slytherin Dungeon (default) - Dark green with mystical vibes
- Matrix Green - Classic terminal hacker aesthetic
- Azure Serenity - Clean blue tones for productivity
- Golden Hour - Warm, sunset-inspired colors

### Terminal Setup
- Fonts: Nerd Fonts recommended for icon support
- Cursor: Block cursor recommended for better visibility
