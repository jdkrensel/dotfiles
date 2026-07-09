#!/bin/bash
# Claude Code status line.
# Line 1: model, working directory, git branch + staged/modified counts (cached per session).
# Line 2: color-coded context-usage bar, percentage, token count, session cost, and duration.

input=$(cat)

RESET=$'\033[0m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
CYAN=$'\033[36m'
GRAY=$'\033[90m'

model=$(echo "$input" | jq -r '.model.display_name // "Claude"')
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // "~"')
dir_name=$(basename "$cwd")
session_id=$(echo "$input" | jq -r '.session_id // "nosession"')

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
    branch=""; staged=""; modified=""
    if git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        branch=$(git -C "$cwd" --no-optional-locks branch --show-current 2>/dev/null)
        staged=$(git -C "$cwd" --no-optional-locks diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
        modified=$(git -C "$cwd" --no-optional-locks diff --numstat 2>/dev/null | wc -l | tr -d ' ')
    fi
    { echo "${branch}|${staged}|${modified}" > "$cache_file"; } 2>/dev/null
else
    { IFS='|' read -r branch staged modified < "$cache_file"; } 2>/dev/null
fi

git_info=""
if [ -n "$branch" ]; then
    git_info=" ${GRAY}|${RESET} ${CYAN}${branch}${RESET}"
    [ "${staged:-0}" -gt 0 ] 2>/dev/null && git_info="${git_info} ${GREEN}+${staged}${RESET}"
    [ "${modified:-0}" -gt 0 ] 2>/dev/null && git_info="${git_info} ${YELLOW}~${modified}${RESET}"
fi

echo "${GRAY}[${model}]${RESET} ${dir_name}${git_info}"

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
