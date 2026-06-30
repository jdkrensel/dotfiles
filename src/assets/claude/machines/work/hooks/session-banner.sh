#!/bin/bash
# SessionStart banner: states which backend this session talks to, so a Max
# session is never mistaken for a Bedrock one. Emits hook JSON on stdout:
# systemMessage is displayed to the user in the UI, additionalContext is
# injected into Claude's context as a standing reminder.
# Registered in ~/.claude/settings.json AND (via a jq one-liner Jesse runs)
# in ~/.claude-bedrock/settings.json.

if [ "$CLAUDE_CODE_USE_BEDROCK" = "1" ]; then
  msg="Backend: AWS Bedrock (BAA-covered) — profile: ${CLAUDE_CONFIG_DIR:-$HOME/.claude}. PHI work is permitted in this session."
else
  msg="Backend: Anthropic commercial (Claude Max plan — NOT BAA-covered) — profile: ${CLAUDE_CONFIG_DIR:-$HOME/.claude}. PHI must never enter this session."
fi

jq -n --arg m "$msg" '{systemMessage: $m, hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $m}}'
exit 0
