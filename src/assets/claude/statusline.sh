#!/bin/bash
# Claude Code status line.
# Line 1: backend, model, working directory, git branch + staged/modified counts (cached per session).
# When the session runs in a linked git worktree, its path gets a line of its own
# (so it stays visible on narrow terminals).
# Line 2: color-coded context-usage bar, percentage, token count, session cost, and duration.

input=$(cat)

RESET=$'\033[0m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
CYAN=$'\033[36m'
GRAY=$'\033[90m'
# xterm-256 orange: the basic 8 have none, and bright-yellow reads too close to
# YELLOW next to the git-modified count. Deliberately a punchier orange than
# Anthropic's brand #D97757, which is muted enough to recede on a dark terminal.
ORANGE=$'\033[38;5;208m'

model=$(echo "$input" | jq -r '.model.display_name // "Claude"')
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // "~"')
dir_name=$(basename "$cwd")
session_id=$(echo "$input" | jq -r '.session_id // "nosession"')

# --- Backend badge ---
# Which service the session actually talks to, so a Max session is never
# mistaken for a Bedrock one. Keyed on the same env var as the SessionStart
# banner (machines/work/hooks/session-banner.sh) so the two can't disagree.
# Green is an affirmative "this is the BAA-covered profile, PHI work is
# permitted"; orange marks the Max profile as the one clinical data must never
# enter. Both are colored on purpose — a gray default would be easy to stop
# seeing, and not-noticing is the exact failure mode this badge guards against.
#
# Shown only where the split exists. This script installs on machines with no
# Bedrock profile, and there the badge would be a permanently-on warning color
# distinguishing nothing — which is how a warning color stops being seen.
backend=""
if [ -d "$HOME/.claude-bedrock" ] || [ -n "$CLAUDE_CODE_USE_BEDROCK" ]; then
    if [ "$CLAUDE_CODE_USE_BEDROCK" = "1" ]; then
        backend="${GREEN}BEDROCK${RESET} "
    else
        backend="${ORANGE}MAX${RESET} "
    fi
fi

# --- Git info: cached per session, refreshed at most every 5s (git status/diff can be slow) ---
# Key the cache by session AND cwd so a directory change doesn't show the
# previous repo's git info for up to 5 seconds.
cwd_key=$(printf '%s' "$cwd" | cksum | cut -d' ' -f1)
cache_file="${TMPDIR:-/tmp}/statusline-git-cache-${session_id}-${cwd_key}"
now=$(date +%s)
cache_age=999
if [ -f "$cache_file" ]; then
    # stat -f %m is macOS/BSD; stat -c %Y is GNU/Linux
    cache_mtime=$(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file" 2>/dev/null || echo 0)
    cache_age=$((now - cache_mtime))
fi

if [ "$cache_age" -ge 5 ]; then
    branch=""; staged=""; modified=""; worktree=""
    if git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        branch=$(git -C "$cwd" --no-optional-locks branch --show-current 2>/dev/null)
        staged=$(git -C "$cwd" --no-optional-locks diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
        modified=$(git -C "$cwd" --no-optional-locks diff --numstat 2>/dev/null | wc -l | tr -d ' ')
        # In a linked worktree the git dir is private (.git/worktrees/<name>) while
        # the common dir stays shared — they only match in the main working tree.
        git_dir=$(git -C "$cwd" --no-optional-locks rev-parse --path-format=absolute --git-dir 2>/dev/null)
        common_dir=$(git -C "$cwd" --no-optional-locks rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
        if [ -n "$git_dir" ] && [ "$git_dir" != "$common_dir" ]; then
            worktree=$(git -C "$cwd" --no-optional-locks rev-parse --show-toplevel 2>/dev/null)
        fi
    fi
    { echo "${branch}|${staged}|${modified}|${worktree}" > "$cache_file"; } 2>/dev/null
else
    { IFS='|' read -r branch staged modified worktree < "$cache_file"; } 2>/dev/null
fi

git_info=""
if [ -n "$branch" ]; then
    git_info=" ${GRAY}|${RESET} ${CYAN}${branch}${RESET}"
    [ "${staged:-0}" -gt 0 ] 2>/dev/null && git_info="${git_info} ${GREEN}+${staged}${RESET}"
    [ "${modified:-0}" -gt 0 ] 2>/dev/null && git_info="${git_info} ${YELLOW}~${modified}${RESET}"
fi

echo "${GRAY}[${RESET}${backend}${GRAY}${model}]${RESET} ${dir_name}${git_info}"
if [ -n "$worktree" ]; then
    wt_display=${worktree/#"$HOME"/\~}
    echo "${GRAY}${wt_display}${RESET}"
fi

# --- Context usage bar (green <70%, yellow 70-89%, red >=90%) ---
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0')
used_int=${used_pct%.*}
[ -z "$used_int" ] && used_int=0

filled=$((used_int / 10))
[ "$filled" -gt 10 ] && filled=10
[ "$filled" -lt 0 ] && filled=0
empty=$((10 - filled))

if [ "$used_int" -ge 90 ]; then
    bar_color="$RED"
elif [ "$used_int" -ge 70 ]; then
    bar_color="$YELLOW"
else
    bar_color="$GREEN"
fi

bar=""
for ((i = 0; i < filled; i++)); do bar="${bar}█"; done
for ((i = 0; i < empty; i++)); do bar="${bar}░"; done

tokens=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
window=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')
tokens_k=$(((tokens + 500) / 1000))
window_k=$(((window + 500) / 1000))

cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
duration_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
duration_s=$((duration_ms / 1000))
mins=$((duration_s / 60))
secs=$((duration_s % 60))

printf "%s%s%s %s%% (%sk/%sk) %s| \$%.2f | %dm %ds%s\n" "$bar_color" "$bar" "$RESET" "$used_int" "$tokens_k" "$window_k" "$GRAY" "$cost" "$mins" "$secs" "$RESET"
