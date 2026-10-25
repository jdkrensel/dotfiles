---
description: Copy a "cd here && clb" command to the clipboard, for opening this directory in the bedrock-profile terminal (max-plan -> bedrock)
allowed-tools: Bash(pwd:*), Bash(echo:*), Bash(pbcopy:*)
profiles: clp
---

## Instructions

Run this exact command using the Bash tool:

echo "cd $(pwd) && clb" | pbcopy

Then tell the user that `cd <directory> && clb` (substituting the actual current directory) has been copied to the clipboard, ready to paste into a new terminal tab.
