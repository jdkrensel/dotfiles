#!/bin/bash
# PHI guard for the Max-plan (locked) default profile. The Max plan is not
# BAA-covered, so clinical data must never enter a session in this profile.
# Registered as a PreToolUse hook in ~/.claude/settings.json.
# The Bedrock profile (~/.claude-bedrock, `clb` alias) has no such hook.
#
# TWO OUTCOMES, and which one applies depends on the TOOL, not just the path:
#
#   deny() -> exit 2. A deterministic block enforced by the harness. Neither
#     the model NOR THE USER can override it; there is no prompt. Used for
#     everything except single-file Read (see below), and unconditionally for
#     credentials, the Bedrock profile, and the DB/log CLIs.
#
#   ask() -> permissionDecision "ask" on stdout. Surfaces a permission prompt
#     the user can approve or decline. Used ONLY for the Read tool on
#     data-export files and personal areas.
#
# Why only Read is promptable: Read names exactly one file, and that path is
# shown in the prompt, so an approval is an informed decision about a specific
# file. Bash/Grep/Glob can sweep a whole directory through one approval (a
# glob, a pipe, a recursive search), so they stay a hard deny — and for Bash
# the OS sandbox denyRead is the real enforcement anyway.
#
# An approval here does NOT make this profile safe for PHI. It exists so a
# file the user has confirmed is redacted (a sample feed, a spec extract) can
# be read without switching profiles. Real patient data still belongs in clb.
#
# WHITELIST: non-PHI dirs that are FULLY readable, including xlsx/csv/parquet:
# the published AAOS/AJRR spec dirs, plus ~/redacted, where the user drops
# outputs they have already redacted by hand so they can be worked on here
# without switching profiles. To whitelist another dir, add it to
# is_whitelisted() below AND, if it sits under a sandbox denyRead root, to
# sandbox.filesystem.allowRead in ~/.claude/settings.json (the kernel
# allowRead overrides both the ~/Documents denyRead and the **/*.xlsx-style
# glob denies — verified 2026-06-12). ~/redacted is under no denyRead root,
# so it needs no allowRead entry (verified 2026-09-18).
#
# The repo entries are deliberately checkout-agnostic (`repos/*/...`): the same
# tree is cloned under several names (sqs_importer, sqs_importer_aaos, …) and
# git worktrees nest another level, so pinning a single clone name silently
# broke the whitelist and made `import aaos.cli` unrunnable — that package
# parses a bundled spec xlsx at import time. The `*` in a bash `case` glob DOES
# cross `/`, so these also cover worktree paths. Keep them anchored at
# $HOME/repos and ending in the spec dir: patient data lives in the repo root
# and in batch dirs, which must stay blocked. Mirror any change here into the
# settings.json allowRead globs (verified 2026-07-29).

input=$(cat)
tool=$(printf '%s' "$input" | jq -r '.tool_name // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')

deny() {
  echo "PHI guard: $1 This profile (Max plan, not BAA-covered) must not touch clinical data. Use the clb (Bedrock) profile for this work." >&2
  exit 2
}

# Prompt the user instead of blocking. stdout must be the JSON decision and the
# exit status must be 0 — a non-zero exit is read as a block and the reason
# never reaches the prompt.
ask() {
  jq -n --arg r "PHI guard: $1 This profile is the Max plan and is NOT BAA-covered. Approve ONLY if you have confirmed this file holds no patient data. For real PHI, decline and use the clb (Bedrock) profile." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
  exit 0
}

is_whitelisted() {
  # A `..` segment anywhere disqualifies the path: normalize() does not resolve
  # them, so a whitelisted prefix followed by `../../..` would otherwise walk
  # back out into ~/Downloads (or anywhere) and be allowed. Never whitelist
  # those — they fall through to the normal denies below.
  case "$1" in
    ../* | */../* | */..) return 1 ;;
  esac
  case "$1" in
    "$HOME/Documents/ajrr_docs" | "$HOME/Documents/ajrr_docs/"*) return 0 ;;
    "$HOME/Documents/asr_docs" | "$HOME/Documents/asr_docs/"*) return 0 ;;
    "$HOME/redacted" | "$HOME/redacted/"*) return 0 ;;
    "$HOME"/repos/*/aaos/registries/*/spec/data | "$HOME"/repos/*/aaos/registries/*/spec/data/*) return 0 ;;
    "$HOME"/repos/*/clients/AJRR_queries | "$HOME"/repos/*/clients/AJRR_queries/*) return 0 ;;
  esac
  return 1
}

normalize() {
  local p="$1"
  p="${p/#\~/$HOME}"
  p="${p/#\$HOME/$HOME}"
  while [ "${p#./}" != "$p" ]; do p="${p#./}"; done
  case "$p" in
    /*) ;;
    *) [ -n "$cwd" ] && p="$cwd/$p" ;;
  esac
  printf '%s' "$p"
}

case "$tool" in
  Bash)
    cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
    if printf '%s' "$cmd" | grep -qiE '(^|[^[:alnum:]_./-])(mysql|mysqlsh|mycli|psql|logcli)([^[:alnum:]_-]|$)'; then
      deny "database/log CLI commands are blocked."
    fi
    if printf '%s' "$cmd" | grep -qiE 'login-path|mylogin\.cnf'; then
      deny "MySQL credential use is blocked."
    fi
    if printf '%s' "$cmd" | grep -qiE '(^|[^[:alnum:]_])(import|from)[[:space:]]+(pymysql|MySQLdb|aiomysql|mysql\.connector)'; then
      deny "inline Python MySQL drivers are blocked."
    fi
    if printf '%s' "$cmd" | grep -qiE 'db\.mcp\.prod|grafana\.caresense\.com'; then
      deny "internal clinical-data hosts are blocked."
    fi
    # Data-export files (.xlsx/.csv/.parquet): blocked unless every referenced
    # path resolves into a whitelisted spec dir. Refs that are bare filename
    # fragments (paths with spaces lose their head when tokenized) pass only
    # if the command also names a whitelisted dir. Best-effort on command
    # text — the OS sandbox glob denyRead is the hard enforcement.
    # Both ref loops below MUST be fed by process substitution, never a heredoc
    # or herestring: bash implements those by writing a temp file, and when it
    # cannot (a restricted or unwritable TMPDIR) the redirect fails, the loop
    # body never runs, and the hook falls through to exit 0 — a silent FAIL-OPEN
    # that allows exactly the read it exists to stop. Process substitution uses
    # /dev/fd and needs no temp file. `< <(...)` also keeps the loop in the
    # current shell, so deny()'s exit 2 still terminates the hook.
    refs=$(printf '%s' "$cmd" | grep -oiE '[^"'"'"'[:space:]]*\.(xlsx|csv|parquet)' || true)
    has_wl_ref=0
    # Keep the registry segment as permissive as the is_whitelisted() globs
    # ([^/]+, not a fixed ajrr|asr list): a narrower pattern here false-denies a
    # spec sheet whose filename contains spaces, since those tokenize down to a
    # slashless fragment that only this check can clear.
    printf '%s' "$cmd" | grep -qE '(~|\$HOME|/Users/jessekrensel)/(Documents/(ajrr_docs|asr_docs)|redacted)/|aaos/registries/[^/]+/spec/data/|clients/AJRR_queries/' && has_wl_ref=1
    if [ -n "$refs" ]; then
      while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        norm=$(normalize "$ref")
        is_whitelisted "$norm" && continue
        # Slash check uses the RAW ref: a bare fragment (tail of a quoted path
        # with spaces) carries no slash and is judged by has_wl_ref instead.
        case "$ref" in
          */*) deny "reading data-export files (.xlsx/.csv/.parquet) outside the whitelisted dirs (spec dirs, ~/redacted) is blocked." ;;
          *) [ "$has_wl_ref" -eq 1 ] || deny "reading data-export files (.xlsx/.csv/.parquet) outside the whitelisted dirs (spec dirs, ~/redacted) is blocked." ;;
        esac
      done < <(printf '%s\n' "$refs")
    elif printf '%s' "$cmd" | grep -qiE 'read_(excel|csv|parquet)|openpyxl|load_workbook'; then
      deny "reading data-export files via Python without a visible whitelisted dir path is blocked."
    fi
    # Personal file areas: Downloads and Desktop are fully blocked; Documents
    # is blocked except the whitelisted spec dirs.
    while IFS= read -r ref; do
      [ -z "$ref" ] && continue
      norm=$(normalize "$ref")
      is_whitelisted "$norm" && continue
      deny "personal file areas (~/Documents, ~/Downloads, ~/Desktop) are blocked except the whitelisted dirs (~/Documents/{ajrr_docs,asr_docs}, ~/redacted)."
    done < <(printf '%s' "$cmd" | grep -oE '(~|\$HOME|/Users/jessekrensel)/(Documents|Downloads|Desktop)[^"'"'"'[:space:]]*' || true)
    ;;
  Read|Grep|Glob)
    path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty')
    norm=$(normalize "$path")
    # Read prompts, Grep/Glob block (see the header for why). Resolving the
    # outcome to a function name up front keeps the path rules below written
    # once — they are identical for both, only the verdict differs.
    verdict=deny
    [ "$tool" = "Read" ] && verdict=ask
    # Never promptable, and deliberately checked BEFORE the whitelist/verdict
    # logic so a .csv sitting under ~/.claude-bedrock denies rather than asks.
    # Matched on the normalized path: a bare filename with cwd inside the
    # profile dir carries no ".claude-bedrock" substring of its own.
    if printf '%s' "$norm" | grep -qiE 'mylogin\.cnf|\.config/loki|\.claude-bedrock'; then
      deny "credential and Bedrock-profile paths are blocked."
    fi
    if ! is_whitelisted "$norm"; then
      if printf '%s' "$path" | grep -qiE '\.(xlsx|csv|parquet)$'; then
        "$verdict" "data-export file (.xlsx/.csv/.parquet) outside the whitelisted dirs (spec dirs, ~/redacted)."
      fi
      case "$norm" in
        "$HOME/Documents" | "$HOME/Documents/"* | "$HOME/Downloads" | "$HOME/Downloads/"* | "$HOME/Desktop" | "$HOME/Desktop/"*)
          "$verdict" "path in a personal file area (~/Documents, ~/Downloads, ~/Desktop) outside ~/Documents/{ajrr_docs,asr_docs}." ;;
      esac
    fi
    ;;
esac

exit 0
