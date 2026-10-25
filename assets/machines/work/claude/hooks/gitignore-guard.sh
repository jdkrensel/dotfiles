#!/bin/bash
# Gitignore read guard. Blocks Read/Grep/Glob of gitignored files, and Bash
# commands whose arguments name an existing gitignored file (best-effort).
# Rationale: gitignored files hold credentials (settings.py, *.env).
# Exit 2 is a deterministic deny enforced by the harness.

set -f  # no globbing while tokenizing commands

input=$(cat)
tool=$(jq -r '.tool_name // empty' <<<"$input")
cwd=$(jq -r '.cwd // empty' <<<"$input")

deny() {
  echo "Gitignore guard: $1 Gitignored files are blocked from being read. If the task genuinely needs this file, stop and ask Jesse." >&2
  exit 2
}

# is_blocked <path>: 0 if path exists, is inside a git repo, and is gitignored.
is_blocked() {
  local p="$1" abs dir
  [ -n "$p" ] || return 1
  while [ "${p#./}" != "$p" ]; do p="${p#./}"; done
  [ -n "$p" ] || return 1
  case "$p" in /*) abs="$p" ;; *) abs="$cwd/$p" ;; esac
  [ -e "$abs" ] || return 1
  if [ -d "$abs" ]; then dir="$abs"; else dir=$(dirname "$abs"); fi
  git -C "$dir" check-ignore -q "$abs" 2>/dev/null
}

case "$tool" in
  Read | Grep | Glob)
    path=$(jq -r '.tool_input.file_path // .tool_input.path // empty' <<<"$input")
    if is_blocked "$path"; then deny "'$path' is gitignored."; fi
    ;;
  Bash)
    cmd=$(jq -r '.tool_input.command // empty' <<<"$input")
    count=0
    for tok in $(printf '%s' "$cmd" | tr -d '"'"'" | tr ';|&()<>\t\n' ' '); do
      count=$((count + 1))
      [ "$count" -gt 200 ] && break
      case "$tok" in -* | *=*) continue ;; esac
      if is_blocked "$tok"; then deny "command references gitignored file '$tok'."; fi
    done
    ;;
esac

exit 0
