#!/usr/bin/env bash
# Grep the CareSense PHP application log on a remote web host.
#
# Usage:
#   phplog.sh <staging|prod> [--all] <grep-pattern> [tail-count]
#   phplog.sh <staging|prod> [--all] --errors [tail-count]
#
#   --all      also search rotated history (phplogfile.log-YYYYMMDD, incl. .gz)
#   --errors   shorthand for WARN/ERROR lines only (the usual triage entry point)
#
# Examples:
#   phplog.sh staging test.csv
#   phplog.sh staging 'WEB_4dtsuq2v56gk96q6ho5doufkt0' 60
#   phplog.sh prod --errors 60
#   phplog.sh prod --all uploadToS3 60
#
# Note: prod log timestamps are Eastern (PHP tz America/New_York); staging is UTC.
#
# Output is prefixed with the matching line number, or with the filename when --all is
# used (hits then span multiple files).
#
# Why this exists: the log path in the tracked repo (/var/log/php) is overridden by a
# gitignored local_settings.php to /usr/local/var/log/php, the remote login shell is
# fish (so commands need a bash -lc wrapper), and the files are large enough that
# filtering must happen server-side.
set -euo pipefail

LOG_DIR=/usr/local/var/log/php
LOG=$LOG_DIR/phplogfile.log

# Print the comment header's usage block as the usage message, so the two can't drift.
# Keyed off the text rather than line numbers so editing the header stays safe.
die() {
  printf 'error: %s\n\n' "$1" >&2
  sed -n '/^# Usage:/,/^# Output is/p' "$0" | sed '$d; s/^# \{0,1\}//' >&2
  exit 1
}

[[ $# -ge 1 ]] || die "missing environment"

case "${1:-}" in
  staging) HOST=www_staging ;;
  prod)    HOST=www_prod ;;
  *)       die "unknown environment '${1}' (expected 'staging' or 'prod')" ;;
esac
shift

ALL=0
if [[ "${1:-}" == "--all" ]]; then ALL=1; shift; fi

PATTERN="${1:-}"
[[ -n $PATTERN ]] || die "missing grep pattern"

if [[ $PATTERN == "--errors" ]]; then
  # Trailing space matters: bare WARN/ERROR also match those words inside message
  # bodies, which inflates counts and pulls in unrelated lines.
  PATTERN='WARN |ERROR '
  GREP_FLAGS=-E
  TAIL="${2:-30}"
else
  GREP_FLAGS=
  TAIL="${2:-30}"
fi

# Single-quote the pattern for the remote shell so spaces and regex metacharacters
# survive; escape any embedded single quotes.
esc_pattern=${PATTERN//\'/\'\\\'\'}

if [[ $ALL -eq 1 ]]; then
  # zgrep transparently handles both gzipped (staging) and plain (prod) rotations.
  # Rotated names sort lexicographically into date order, so a plain glob reads
  # oldest-first with the live log last. Deliberately a glob and not $(ls ...):
  # the remote login shell is fish, which would expand a command substitution
  # itself before bash ever sees it.
  remote="cd $LOG_DIR && zgrep $GREP_FLAGS -H '$esc_pattern' phplogfile.log-* phplogfile.log 2>/dev/null | tail -$TAIL"
else
  remote="grep $GREP_FLAGS -n '$esc_pattern' $LOG | tail -$TAIL"
fi

# grep exits 1 on no match; report that as a clear message rather than a bare failure,
# since "not found here" has several distinct causes worth checking (see SKILL.md).
set +e
output=$(ssh -o ConnectTimeout=10 "$HOST" "bash -lc \"$remote\"" 2>&1 | grep -v fnm_multishells)
set -e

if [[ -z ${output// /} ]]; then
  echo "No matches for '$PATTERN' in $LOG on $HOST." >&2
  if [[ $ALL -eq 0 ]]; then
    echo "Rotated history was not searched — retry with --all to include it." >&2
    echo "Note: rotation suffixes are the rotation date, so yesterday's lines are in the file dated today." >&2
  fi
  exit 1
fi

printf '%s\n' "$output"
