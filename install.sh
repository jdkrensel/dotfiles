#!/bin/zsh

setopt err_exit      # Exit immediately if a command exits with a non-zero status
setopt nounset       # Treat unset variables as an error when substituting
setopt pipefail      # The return status of a pipeline is the status of the last command to exit with a non-zero status

# --- Color definitions ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# --- Utility functions ---
print_header() {
    local title="$1"
    echo "\n${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo "${CYAN}║${NC}  ${WHITE}$1${NC}"
    echo "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
}

print_step() {
    echo "\n${BLUE}▶${NC} ${WHITE}$1${NC}"
}

print_success() {
    echo "${GREEN}✓${NC} $1"
}

print_info() {
    echo "${YELLOW}ℹ${NC} $1"
}

print_error() {
    echo "${RED}✗${NC} $1"
}

# --- Preamble: Check for zsh and define key variables ---

# Exit if the current shell is not zsh
if [[ -z "$ZSH_VERSION" ]]; then
    print_error "This script is meant to be run in zsh. Exiting."
    exit 1
fi

# Get the directory where the script is located
DOTFILES_DIR="${0:a:h}"

# Welcome message
echo "\n${PURPLE}╭──────────────────────────────────────────────────────────────╮${NC}"
echo "${PURPLE}│${NC}  ${WHITE}🚀 Welcome to the Dotfiles Installation Script! 🚀${NC}"
echo "${PURPLE}│${NC}  ${WHITE}This will set up your development environment${NC}"
echo "${PURPLE}╰──────────────────────────────────────────────────────────────╯${NC}"

# --- Section 0: Get User Information ---
print_header "User Configuration"

print_step "Getting your name for the terminal banner..."
read -r "USER_NAME?Enter your first name (or press Enter to use 'jesse'): "
USER_NAME=${USER_NAME:-jesse}
print_success "Using name: $USER_NAME"

# --- Section 1: Prerequisites Check and Installation ---
print_header "Checking Prerequisites"

print_step "Checking for Homebrew..."
if ! command -v brew &>/dev/null; then
    print_info "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    exec "$0" "$@"
else
    print_success "Homebrew is already installed"
fi

print_step "Checking for Rust..."
if ! command -v cargo &>/dev/null; then
    print_info "Rust not found. Installing Rust via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    source "$HOME/.cargo/env"
else
    print_success "Rust is already installed"
fi

# --- Section 2: Install from Brewfile ---
print_header "Installing Homebrew Packages"

print_step "Installing packages from Brewfile..."
# Note: The Brewfile is now inside the 'src' directory
brew bundle --file="$DOTFILES_DIR/src/Brewfile"
print_success "Homebrew packages installed successfully"

# --- Section 3: Symlinking specific dotfiles ---
print_header "Setting Up Configuration Files"

print_step "Creating symlinks for configuration files..."

# Define the source directory for configuration files
SOURCE_DIR="$DOTFILES_DIR/src"

# Define an array of files to symlink
files_to_symlink=("zshrc" "gitconfig")

# Loop through the array and create symlinks
for file in "${files_to_symlink[@]}"; do
    src_file="$SOURCE_DIR/$file"
    dest_path="$HOME/.$file"

    if [[ -f "$src_file" ]]; then
        if [[ -f "$dest_path" ]]; then
            # Check if it's already a symlink to the correct location
            if [[ -L "$dest_path" ]] && [[ "$(readlink "$dest_path")" == "$src_file" ]]; then
                print_info "Existing .$file is already symlinked to dotfiles, updating..."
                ln -sf "$src_file" "$dest_path"
                print_success "Updated symlink for .$file"
            else
                print_info "Existing .$file found at $dest_path"
                read -r "BACKUP_CHOICE?Create backup to .$file.bak? (y/n): "
                if [[ "$BACKUP_CHOICE" =~ ^[Yy]$ ]]; then
                    mv "$dest_path" "$dest_path.bak"
                    print_success "Created backup: .$file.bak"
                    ln -sf "$src_file" "$dest_path"
                    print_success "Created symlink for .$file"
                else
                    print_info "Skipping .$file (keeping existing file)"
                fi
            fi
        else
            ln -sf "$src_file" "$dest_path"
            print_success "Created symlink for .$file"
        fi
    else
        print_error "Source file not found: $src_file"
    fi
done

# --- Section 3.5: Create local zsh configuration ---
print_step "Creating local zsh configuration with your name..."
cat > "$HOME/.zshrc.local" << EOF
# Local zsh configuration
export USER_NAME="$USER_NAME"
EOF
print_success "Created .zshrc.local with USER_NAME=$USER_NAME"

# --- Section 4: Final steps ---
print_header "Installation Complete"

echo "\n${GREEN}🎉 All done! Your dotfiles have been successfully installed! 🎉${NC}"
echo "\n${YELLOW}Next steps:${NC}"
echo "  ${WHITE}•${NC} Restart your terminal for all changes to take effect"
echo "  ${WHITE}•${NC} Or run: ${CYAN}source ~/.zshrc${NC}"
echo "  ${WHITE}•${NC} Your name '$USER_NAME' has been configured in the terminal banner"
echo "  ${WHITE}•${NC} **Important:** See the **README.md** for manual terminal setup instructions."
echo "\n"