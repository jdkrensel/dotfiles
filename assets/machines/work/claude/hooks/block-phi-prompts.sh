#!/bin/bash
# block-phi-prompts.sh — UserPromptSubmit hook (work machine, Max profile)
#
# Does: rejects a prompt that holds pasted SQL query results or PHI-shaped
#       text, BEFORE it reaches Anthropic.
# Why:  the Max plan is not BAA-covered, so PHI must never reach it.
# Runs: UserPromptSubmit, registered in the machine-local
#       ~/.claude/settings.json of the Max-plan (locked) default profile.
# Exit: 2 = reject (the prompt is erased, never sent); 0 = send.
# Pair: block-phi-tool-calls.sh guards tool calls for the same reason.
#
# This is a confirmation gate, not a ban: if the content is genuinely not PHI,
# recall the prompt (up-arrow) and resubmit it with "no-phi:" as the first
# line's prefix to bypass all checks.
#
# Known limits: only sees prompt TEXT — pasted images/screenshots pass through
# uninspected, and `!`-prefix command output does not pass through this hook.

input=$(cat)
prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')

# Explicit user confirmation bypasses all checks. Only the FIRST line counts:
# grep anchors ^ per line, so without head the token would be honoured anywhere
# in the prompt — and "no-phi:" is an ordinary YAML key, so a pasted blob
# containing one would silently switch off every check below.
if printf '%s\n' "$prompt" | head -n 1 | grep -qiE '^[[:space:]]*no-phi:'; then
  exit 0
fi

deny() {
  echo "Prompt guard: $1 The prompt was NOT sent to Anthropic. If it contains no PHI, press up-arrow to recall it and resubmit prefixed with 'no-phi:'." >&2
  exit 2
}

# SSN-shaped numbers.
if printf '%s' "$prompt" | grep -qE '\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b'; then
  deny "this looks like it contains an SSN."
fi

# Explicit MRN references.
if printf '%s' "$prompt" | grep -qiE '\bMRN[[:space:]#:]*[0-9]{5,}'; then
  deny "this looks like it contains an MRN."
fi

# mysql/psql console table output: +----+ border lines or a "rows in set" footer.
if [ "$(printf '%s\n' "$prompt" | grep -cE '^\+[-+]+\+$')" -ge 2 ] \
   || printf '%s' "$prompt" | grep -qiE '[0-9]+ rows? in set'; then
  deny "this looks like pasted SQL query output."
fi

# Bulk tabular data: 10+ lines that each carry 4+ tab or 4+ pipe delimiters.
tabbed=$(printf '%s\n' "$prompt" | grep -cE '(.*	){4,}')
piped=$(printf '%s\n' "$prompt" | grep -cE '(.*\|){4,}')
if [ "$tabbed" -ge 10 ] || [ "$piped" -ge 10 ]; then
  deny "this looks like bulk tabular data (possible patient rows)."
fi

exit 0
