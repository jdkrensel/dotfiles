# Dotfiles

A modern dotfiles installer that sets up a comprehensive development environment on macOS.

## Quick Start

### Prerequisites
- macOS on Apple Silicon
- zsh as your login shell (the macOS default since Catalina)
- Homebrew (installed automatically if needed)
- [uv](https://docs.astral.sh/uv/), which runs the installer on the Python 3.14 it requires:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Installation

```bash
# Clone the repository
git clone https://github.com/jdkrensel/dotfiles.git
cd dotfiles

# Run the installer
uv run -m installer
```

### Inspecting before installing

Three read-only ways to inspect what the installer would do. None of them
writes anything.

```bash
uv run -m installer --dry-run # walk the real install with every write suppressed
uv run -m installer resolve   # where each tracked asset is linked
uv run -m installer doctor    # drift an install would not fix on its own
```

`resolve` takes `--group` to narrow to one collection (`home`, `rules`, `agents`,
`commands`, `skills`, `hooks`, `statusline`, `local-commands`, `local-skills`).
`doctor` exits non-zero when it finds something, so it can gate a script.

`--dry-run` covers the whole configuration phase — the shell files, `~/.config`,
the Claude assets and the `settings.json` merge. It previews that phase only;
the zsh check and the dependency phases (Homebrew, Rust, uv, Claude Code,
opencode) are skipped rather than simulated, since what they would do depends
on what their own package managers decide at run time.

## What Gets Installed

### System Tools
- `Claude Code` - Anthropic's official CLI for Claude AI
- `Homebrew` - Package manager for macOS
- `opencode` - Terminal coding agent, installed via its native installer so `opencode upgrade` works
- `Rust` - Systems programming language and toolchain
- `uv` - Fast Python package installer and resolver

### Homebrew Packages
- `eza` - Modern ls replacement with icons and git status
- `fd` - Fast, user-friendly find alternative
- `ripgrep` - Ultra-fast text search tool
- `starship` - Cross-shell prompt with git integration
- `vivid` - LS_COLORS generator for better file type colors
- `zsh-autosuggestions` - Fish-like autosuggestions for zsh
- `zsh-syntax-highlighting` - Real-time syntax highlighting

### Cask Applications
- `ghostty` - GPU-accelerated terminal emulator
- `zed` - Fast, collaborative code editor

### Shell Enhancements
- Custom aliases for git, navigation, and system operations
- Fish-like autosuggestions with zsh-autosuggestions
- Real-time command highlighting with zsh-syntax-highlighting
- Starship prompt with git status and directory info
- Multiple startup themes (Slytherin, Matrix, Azure, Golden Hour)

### Claude Skills
Shared skills in `assets/claude/skills/` are linked into every Claude profile on every machine.

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
