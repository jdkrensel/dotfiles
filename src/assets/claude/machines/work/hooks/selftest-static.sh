#!/bin/bash
# Static guard self-test for the locked Max profile, run on SessionStart
# (startup). Verifies the PHI safeguards in ~/.claude are intact after Claude
# Code updates or accidental edits. Non-blocking: failures are shown to the
# user (stderr) and injected into Claude's context (stdout).
# The dynamic probe suite (real sandbox/network checks via headless sessions)
# is ~/.claude/hooks/selftest-full.sh — run it manually after CC updates.

# Never run in the Bedrock profile.
[ "$CLAUDE_CODE_USE_BEDROCK" = "1" ] && exit 0
case "$CLAUDE_CONFIG_DIR" in ''|"$HOME/.claude") ;; *) exit 0 ;; esac

S="$HOME/.claude/settings.json"
fails=""
fail() { fails="${fails}  - $1\n"; }

if ! jq -e . "$S" >/dev/null 2>&1; then
  fail "settings.json is missing or not valid JSON (ALL guards from it may be off)"
else
  [ "$(jq -r '.sandbox.enabled' "$S")" = "true" ] || fail "sandbox.enabled is not true"
  [ "$(jq -r '.sandbox.network.allowedDomains | length' "$S")" = "0" ] || fail "sandbox network allowlist is not empty (should be zero-egress)"
  for rule in 'Read(**/*.xlsx)' 'Read(**/*.csv)' 'Read(**/*.parquet)' 'Read(~/Downloads/**)' 'Read(~/Desktop/**)' 'Bash(mysql *)' 'Bash(logcli *)'; do
    jq -e --arg r "$rule" '.permissions.deny | index($r)' "$S" >/dev/null || fail "permissions.deny rule missing: $rule"
  done
  # The spec-sheet carve-outs must stay readable, or `import aaos.cli` breaks —
  # that package parses a bundled spec xlsx at import time. Two properties are
  # asserted per carve-out, matched on shape rather than exact text so an
  # equivalent rewrite doesn't cry wolf:
  #   1. it must not pin one clone name (the tree is cloned under several, and
  #      git worktrees nest a level deeper);
  #   2. a GLOB entry must end in a subtree suffix. A glob is rendered as an
  #      anchored regex, so a bare-directory glob matches only the directory
  #      path itself and does NOT re-allow the files inside it.
  for frag in 'aaos/registries/[^/]*/spec/data' 'clients/AJRR_queries'; do
    hits=$(jq -r --arg f "$frag" '[.sandbox.filesystem.allowRead[]? | select(test($f))] | .[]' "$S" 2>/dev/null)
    if [ -z "$hits" ]; then
      fail "sandbox.filesystem.allowRead has no entry for $frag (spec sheets unreadable)"
      continue
    fi
    printf '%s' "$hits" | grep -q 'sqs_importer[^/]*/' &&
      fail "sandbox.filesystem.allowRead pins a clone name for $frag (breaks other checkouts/worktrees)"
    printf '%s' "$hits" | grep -qE '\*' && ! printf '%s' "$hits" | grep -qE '/\*\*/\*$|/\*\*$' &&
      fail "sandbox.filesystem.allowRead glob for $frag lacks a /**/* subtree suffix (dir matches, files do not)"
  done
  for dir in ajrr_docs asr_docs; do
    jq -e --arg d "~/Documents/$dir" '.sandbox.filesystem.allowRead | index($d)' "$S" >/dev/null ||
      fail "sandbox.filesystem.allowRead missing ~/Documents/$dir (spec documents unreadable)"
  done
  reg=$(jq -r '[(.hooks.PreToolUse // [])[].hooks[].command, (.hooks.UserPromptSubmit // [])[].hooks[].command] | join("\n")' "$S" 2>/dev/null)
  for h in phi-guard.sh gitignore-guard.sh prompt-guard.sh; do
    printf '%s' "$reg" | grep -q "$h" || fail "hook not registered in settings.json: $h"
    [ -x "$HOME/.claude/hooks/$h" ] || fail "hook script missing or not executable: $h"
  done
  # Surface the weekly dynamic probe suite's verdict (launchd appends to the
  # log). Warn on failure or if it has not run in over 8 days. Skipped when
  # invoked FROM selftest-full.sh, which writes its RESULT line only at the
  # end of the run (the check would be circular there).
  if [ -z "${SELFTEST_SKIP_LOG_CHECK:-}" ]; then
  log="$HOME/.claude/selftest-full.log"
  last=$(grep '^RESULT ' "$log" 2>/dev/null | tail -1)
  if [ -z "$last" ]; then
    fail "dynamic probe suite has never run (selftest-full.sh)"
  else
    printf '%s' "$last" | grep -q 'ALL PASS' || fail "last dynamic probe run FAILED: $last"
    last_date=$(printf '%s' "$last" | awk '{print $2}')
    last_epoch=$(date -j -f %Y-%m-%d "$last_date" +%s 2>/dev/null || echo 0)
    if [ $(( ($(date +%s) - last_epoch) / 86400 )) -gt 8 ]; then
      fail "dynamic probe suite is stale (last run $last_date) — run ~/.claude/hooks/selftest-full.sh"
    fi
  fi
  fi
  # Strict mode is planned for 2026-06-18 after a week of friction-free use;
  # nag from that date until the keys are flipped.
  if [ "$(date +%Y%m%d)" -ge 20260618 ]; then
    [ "$(jq -r '.sandbox.allowUnsandboxedCommands' "$S")" = "false" ] || fail "strict mode pending: set sandbox.allowUnsandboxedCommands=false (planned 2026-06-18)"
    [ "$(jq -r '.sandbox.failIfUnavailable' "$S")" = "true" ] || fail "strict mode pending: set sandbox.failIfUnavailable=true (planned 2026-06-18)"
  fi
fi

if [ -n "$fails" ]; then
  # JSON output: systemMessage is displayed in the UI, additionalContext goes
  # into Claude's context (plain stdout is NOT shown to the user on SessionStart).
  msg=$(printf 'GUARD SELFTEST FAILED — PHI safeguards may be degraded:\n%b' "$fails")
  jq -n --arg m "$msg" '{systemMessage: $m, hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $m}}'
else
  echo "Guard selftest: all PHI safeguards intact."
fi
exit 0
