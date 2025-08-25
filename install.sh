#!/usr/bin/env zsh

# --- Shell Detection and Switching ---
# Check if we're already running in zsh
if [[ -z "$ZSH_VERSION" ]]; then
    # We're not in zsh, so we need to switch
    if command -v zsh &>/dev/null; then
        echo "Switching to zsh shell..."
        exec zsh "$0" "$@"
    else
        echo "Error: zsh is not installed. Please install zsh first."
        exit 1
    fi
fi

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

# --- Preamble: Define key variables ---

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
    
    # Install build-essential on WSL/Linux for Homebrew compilation
    if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "linux"* ]]; then
        if command -v apt-get &>/dev/null; then
            print_info "Installing build-essential for Homebrew compilation..."
            sudo apt-get update
            sudo apt-get install -y build-essential
            print_success "build-essential installed"
        fi
    fi
    
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Set up Homebrew environment variables
    if [[ -f "/home/linuxbrew/.linuxbrew/bin/brew" ]]; then
        print_info "Setting up Homebrew environment variables..."
        eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
        # Add to PATH for current session
        export PATH="/home/linuxbrew/.linuxbrew/bin:$PATH"
        print_success "Homebrew environment configured"
    elif [[ -f "/opt/homebrew/bin/brew" ]]; then
        print_info "Setting up Homebrew environment variables..."
        eval "$(/opt/homebrew/bin/brew shellenv)"
        print_success "Homebrew environment configured"
    else
        print_error "Homebrew installation path not found. Please restart your terminal and run the script again."
        exit 1
    fi
else
    print_success "Homebrew is already installed"
fi



print_step "Checking for Rust..."
if ! command -v cargo &>/dev/null; then
    print_info "Rust not found. Installing Rust via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    print_success "Rust is already installed"
fi

print_step "Checking for nvm..."
# Check if nvm is already installed by looking for the directory and script
if [[ -d "$HOME/.nvm" && -f "$HOME/.nvm/nvm.sh" ]]; then
    print_success "nvm is already installed"
else
    print_info "nvm not found. Installing nvm..."
    # Download installer and run with aggressive profile prevention
    curl -o /tmp/nvm-install.sh https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh
    # Run with multiple prevention methods
    PROFILE=/dev/null NVM_PROFILE=/dev/null bash /tmp/nvm-install.sh
    rm /tmp/nvm-install.sh
    print_info "Note: You can ignore the 'Profile not found' warnings above - this is expected and prevents .zshrc modification."
    print_success "nvm installed successfully"
fi

# --- Section 2: Install from Brewfile ---
print_header "SInstalling Homebrew Packages"

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
files_to_symlink=("zshrc" "gitconfig" "vimrc")

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



# --- Section 4: Final steps ---
print_header "Installation Complete"

echo "\n${GREEN}🎉 Installation complete! 🎉${NC}"

print_step "Reloading shell to apply all changes..."
exec zsh