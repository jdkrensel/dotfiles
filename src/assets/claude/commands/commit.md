---
description: Create a conventional commit
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git commit:*), Bash(git add:*), Bash(git restore:*), Agent(reviewer), Agent(reviewer-quick)
---

## Context

- Git status: !`git status`
- Staged and unstaged changes: !`git diff HEAD`
- Recent commits for style reference: !`git log --oneline -10`
- Diff size, tracked files only (for review routing): !`git diff HEAD --shortstat`
- Untracked files with line counts, NOT counted in the diffstat above (`-uall` so a new directory lists its files rather than collapsing to one entry): !`git status --porcelain -uall | grep '^??' | cut -c4- | tr '\n' '\0' | xargs -0 -r wc -l 2>/dev/null || echo "  none"`

## Instructions

Create a conventional commit for only the files relevant to what we've been working on in this conversation. Do NOT blindly commit all changed files — ignore unrelated changes.

### Step 0 — Stateless review (do this before proposing the commit)

Once you've decided which files to commit, get an unbiased review of them from an
agent that hasn't seen this conversation before finalizing — you wrote this code, so
you're the wrong one to catch its blind spots.

1. **Pick the tier** using the rules below, then **spawn that subagent** (Agent tool)
   and tell it exactly which files are being committed. It runs with no state from
   this session — do NOT paste your rationale; let it inspect the diff itself.
2. **Act on the findings**: fix anything `blocking` or `should-fix` before
   committing (this may change the files you commit). For findings you consciously
   disagree with, note why in one line rather than silently ignoring them. Surface
   the review outcome to the user as part of the plan below, naming which tier ran.
   **An `ESCALATE` is not a finding to act on and not a pass** — re-run with the full
   `reviewer` and act on *that* result instead. Treat as `ESCALATE` any reply that
   neither begins with `LGTM` nor itemizes findings by severity, including one
   truncated by its turn limit, and treat a subagent that fails to run at all the
   same way. Absence of findings is not a pass.

**Which tier — evaluate these in order and take the first that matches:**

1. **`reviewer` (full pass)** if any escalation trigger below fires. Triggers win over
   every other rule here, including the skip branch.
2. **Skip entirely** if the change is inert — prose docs, comments, formatting, version
   bumps — meaning nothing about it changes behavior at runtime. Note "skipping review
   — inert change" and proceed.
   **Markdown is not automatically inert in this repo**: agent, command, skill, and
   hook definitions are executable prompts, and a wrong line in one misroutes real
   work. Route those by their content like any other logic.
3. **`reviewer-quick`** if the diff is small — roughly under 50 changed lines across
   at most 3 files, counting untracked files as their full length.
4. **`reviewer`** for everything else.

**Escalation triggers** — the diff:

- adds a new **code** file, or a new **executable prompt** — an agent, command, skill,
  or hook definition — regardless of length. A genuinely inert new file (prose docs,
  fixtures) is the one exception and may take the skip branch;
- changes a function signature, return shape, or public interface;
- changes control flow or error handling — new branches, changed exception paths,
  removed guards or cleanup;
- touches concurrency, auth, permissions, migrations, money, or PHI-handling code;
- is one you cannot confidently classify.

**Ambiguity resolves to the full `reviewer`.** The failure modes are not symmetric: a
slow review costs minutes, a missed bug costs more. Do not talk yourself into the quick
tier because the diff *looks* small — apply the triggers literally.

Then proceed to the commit itself:

Follow these rules exactly:

1. **Scope to conversation work**: Look at the conversation history to determine which files you touched. Only commit those files. If a file shows up in the diff but wasn't part of our work, leave it alone.
2. **Conventional commit format**: `type(scope): description` where type is one of: feat, fix, chore, docs, style, refactor, perf, test, build, ci
3. **No Co-Authored-By line**. Do not add any trailers to the commit message.
4. **Show the plan first**: Before running any git commands, show the user:
   - The review outcome from Step 0 (the reviewer's verdict and how you handled any findings), or that review was skipped and why
   - The files you will commit
   - The exact commit message
   - Then ask "Look good?" and wait for confirmation before proceeding.
5. **For tracked files**: `git commit -m "type(scope): message" -- path/to/file1 path/to/file2`
6. **For new (untracked) files**: `git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "type(scope): message" -- path/to/file1 path/to/file2`
7. **For a mix of tracked and untracked**: Stage untracked files first with git add, then commit all with explicit paths.
