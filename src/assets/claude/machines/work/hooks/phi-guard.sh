#!/bin/bash
# PHI guard for the Max-plan (locked) default profile. The Max plan is not
# BAA-covered, so clinical data must never enter a session in this profile.
# Registered as a PreToolUse hook in ~/.claude/settings.json; exit 2 is a
# deterministic deny enforced by the harness (the model cannot override it).
# The Bedrock profile (~/.claude-bedrock, `clb` alias) has no such hook.
#
# WHITELIST: non-PHI spec dirs that are FULLY readable, including
# xlsx/csv/parquet. To whitelist another dir, add it to is_whitelisted()
# below AND to sandbox.filesystem.allowRead in ~/.claude/settings.json
# (the kernel allowRead overrides both the ~/Documents denyRead and the
# **/*.xlsx-style glob denies — verified 2026-06-12).

input=$(cat)
tool=$(printf '%s' "$input" | jq -r '.tool_name // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')

deny() {
  echo "PHI guard: $1 This profile (Max plan, not BAA-covered) must not touch clinical data. Use the clb (Bedrock) profile for this work." >&2
  exit 2
}

is_whitelisted() {
  case "$1" in
    "$HOME/Documents/ajrr_docs" | "$HOME/Documents/ajrr_docs/"*) return 0 ;;
    "$HOME/Documents/asr_docs" | "$HOME/Documents/asr_docs/"*) return 0 ;;
    "$HOME/repos/sqs_importer/aaos/registries/ajrr/spec/data" | "$HOME/repos/sqs_importer/aaos/registries/ajrr/spec/data/"*) return 0 ;;
    "$HOME/repos/sqs_importer/aaos/registries/asr/spec/data" | "$HOME/repos/sqs_importer/aaos/registries/asr/spec/data/"*) return 0 ;;
    "$HOME/repos/sqs_importer/clients/AJRR_queries" | "$HOME/repos/sqs_importer/clients/AJRR_queries/"*) return 0 ;;
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
    refs=$(printf '%s' "$cmd" | grep -oiE '[^"'"'"'[:space:]]*\.(xlsx|csv|parquet)' || true)
    has_wl_ref=0
    printf '%s' "$cmd" | grep -qE '(~|\$HOME|/Users/jessekrensel)/Documents/(ajrr_docs|asr_docs)/|aaos/registries/(ajrr|asr)/spec/data/|clients/AJRR_queries/' && has_wl_ref=1
    if [ -n "$refs" ]; then
      while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        norm=$(normalize "$ref")
        is_whitelisted "$norm" && continue
        # Slash check uses the RAW ref: a bare fragment (tail of a quoted path
        # with spaces) carries no slash and is judged by has_wl_ref instead.
        case "$ref" in
          */*) deny "reading data-export files (.xlsx/.csv/.parquet) outside the whitelisted spec dirs is blocked." ;;
          *) [ "$has_wl_ref" -eq 1 ] || deny "reading data-export files (.xlsx/.csv/.parquet) outside the whitelisted spec dirs is blocked." ;;
        esac
      done <<EOF
$refs
EOF
    elif printf '%s' "$cmd" | grep -qiE 'read_(excel|csv|parquet)|openpyxl|load_workbook'; then
      deny "reading data-export files via Python without a visible whitelisted spec-dir path is blocked."
    fi
    # Personal file areas: Downloads and Desktop are fully blocked; Documents
    # is blocked except the whitelisted spec dirs.
    while IFS= read -r ref; do
      [ -z "$ref" ] && continue
      norm=$(normalize "$ref")
      is_whitelisted "$norm" && continue
      deny "personal file areas (~/Documents, ~/Downloads, ~/Desktop) are blocked except ~/Documents/{ajrr_docs,asr_docs}."
    done < <(printf '%s' "$cmd" | grep -oE '(~|\$HOME|/Users/jessekrensel)/(Documents|Downloads|Desktop)[^"'"'"'[:space:]]*' || true)
    ;;
  Read|Grep|Glob)
    path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty')
    norm=$(normalize "$path")
    if ! is_whitelisted "$norm"; then
      if printf '%s' "$path" | grep -qiE '\.(xlsx|csv|parquet)$'; then
        deny "data-export files (.xlsx/.csv/.parquet) are blocked outside the whitelisted spec dirs."
      fi
    fi
    if printf '%s' "$path" | grep -qiE 'mylogin\.cnf|\.config/loki|\.claude-bedrock'; then
      deny "credential and Bedrock-profile paths are blocked."
    fi
    case "$norm" in
      "$HOME/Documents" | "$HOME/Documents/"* | "$HOME/Downloads" | "$HOME/Downloads/"* | "$HOME/Desktop" | "$HOME/Desktop/"*)
        is_whitelisted "$norm" || deny "personal file areas (~/Documents, ~/Downloads, ~/Desktop) are blocked except ~/Documents/{ajrr_docs,asr_docs}." ;;
    esac
    ;;
esac

exit 0
