---
description: Create a conventional commit
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git commit:*), Bash(git add:*), Bash(git restore:*)
---

## Context

- Git status: !`git status`
- Staged and unstaged changes: !`git diff HEAD`
- Recent commits for style reference: !`git log --oneline -10`

## Instructions

Create a conventional commit for only the files relevant to what we've been working on in this conversation. Do NOT blindly commit all changed files — ignore unrelated changes.

Follow these rules exactly:

1. **Scope to conversation work**: Look at the conversation history to determine which files you touched. Only commit those files. If a file shows up in the diff but wasn't part of our work, leave it alone.
2. **Conventional commit format**: `type(scope): description` where type is one of: feat, fix, chore, docs, style, refactor, perf, test, build, ci
3. **No Co-Authored-By line**. Do not add any trailers to the commit message.
4. **Show the plan first**: Before running any git commands, show the user:
   - The files you will commit
   - The exact commit message
   - Then ask "Look good?" and wait for confirmation before proceeding.
5. **For tracked files**: `git commit -m "type(scope): message" -- path/to/file1 path/to/file2`
6. **For new (untracked) files**: `git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "type(scope): message" -- path/to/file1 path/to/file2`
7. **For a mix of tracked and untracked**: Stage untracked files first with git add, then commit all with explicit paths.
