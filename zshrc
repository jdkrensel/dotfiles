source ~/dotfiles/aliases

#------------------------------------------------------------------
# Autocompletion
#------------------------------------------------------------------

# Load the completion system
autoload -Uz compinit
compinit

# Use a menu for completion selection
zstyle ':completion:*' menu select

# Make completion case-insensitive
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'

# Group completions by type
zstyle ':completion:*' group-name ''

#------------------------------------------------------------------
# Package configurations
# -----------------------------------------------------------------

# Configure starship
eval "$(starship init zsh)"

# Configure zoxide
eval "$(zoxide init zsh)"

# Configure fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# Configure cargo
. "$HOME/.cargo/env"

#------------------------------------------------------------------
# Startup Message
#------------------------------------------------------------------
cat <<-EOF
--------------------------------------------------
Welcome back, Jesse!

It's currently $(date +"%A, %B %d, %Y - %r")

EOF

# Cowsays Moo Message
#if command -v fortune &> /dev/null && command -v cowsay &> /dev/null; then
#    fortune | cowsay
#fi

# Neofetch
neofetch

cat <<-EOF
--------------------------------------------------
EOF

#------------------------------------------------------------------
# History Settings 
#------------------------------------------------------------------
HISTSIZE=10000                  # How many lines of history to keep in memory
SAVEHIST=10000                  # How many lines to save to the history file
HISTFILE=~/.zsh_history         # Where to save history
setopt INC_APPEND_HISTORY       # Append commands to history immediately
setopt SHARE_HISTORY            # Share history between all open terminals
setopt HIST_IGNORE_ALL_DUPS     # If you type the same command twice in a row, only save it once
setopt HIST_IGNORE_SPACE        # Commands starting with a space are not saved to history
setopt HIST_FIND_NO_DUPS        # When searching, don't show repeated commands
