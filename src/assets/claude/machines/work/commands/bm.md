---
description: Copy a "cd here && clp" command to the clipboard, for opening this directory in the max-plan-profile terminal (bedrock -> max-plan)
allowed-tools: Bash(pwd:*), Bash(echo:*), Bash(pbcopy:*)
profiles: clb
---

## Instructions

Run this exact command using the Bash tool:

echo "cd $(pwd) && clp" | pbcopy

Then tell the user that `cd <directory> && clp` (substituting the actual current directory) has been copied to the clipboard, ready to paste into a new terminal tab.
