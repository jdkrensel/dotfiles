source ~/dotfiles/aliases

#------------------------------------------------------------------
# Autocompletion System
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
