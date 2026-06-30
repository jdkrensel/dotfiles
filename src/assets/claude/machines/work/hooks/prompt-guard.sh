#!/bin/bash
# Prompt guard for the Max-plan (locked) default profile: catches pasted SQL
# query results / PHI-shaped text BEFORE the prompt is sent to Anthropic.
# Registered as a UserPromptSubmit hook in ~/.claude/settings.json; exit 2
# rejects the prompt (it is erased, never sent).
#
# This is a confirmation gate, not a ban: if the content is genuinely not PHI,
# recall the prompt (up-arrow) and resubmit it prefixed with
# "confirmed-no-phi:" to bypass all checks.
#
# Known limits: only sees prompt TEXT — pasted images/screenshots are not
# inspected, and `!`-prefix command output does not pass through this hook.

input=$(cat)
prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')

# Explicit user confirmation bypasses all checks.
if printf '%s' "$prompt" | grep -qiE '^[[:space:]]*confirmed-no-phi:'; then
  exit 0
fi

deny() {
  echo "Prompt guard: $1 The prompt was NOT sent to Anthropic. If it contains no PHI, press up-arrow to recall it and resubmit prefixed with 'confirmed-no-phi:'." >&2
  exit 2
}

# Pasted images: the TUI inserts an [Image #N] chip into the prompt text.
# Images cannot be inspected for PHI (screenshots of patient lists are the
# classic accident), so every image paste requires explicit confirmation.
if printf '%s' "$prompt" | grep -qE '\[Image #[0-9]+\]'; then
  deny "this contains a pasted image, which cannot be inspected for PHI."
fi

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
