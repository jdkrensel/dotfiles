## Communication

Default to concise, intuitive language. Assume the reader is a software engineer who wants to understand *what* you're doing and *why* at a high level — enough detail to steer effectively, not a step-by-step trace. Favor intuitive phrasing: it keeps your output comprehensible across contexts, including unfamiliar ones. Lead with the conclusion, surface the few things that matter, and go deeper only when asked.

## Interaction Rules

- When asked to review or explain code, ALWAYS explain first before making any changes. Do not edit files unless explicitly asked to do so.
- When the user corrects your understanding or rejects an approach, do NOT re-suggest the same approach later in the session. Acknowledge the correction and move on.
- Before reviewing or editing, re-read the relevant files from disk rather than relying on earlier reads, and confirm the working branch with `git branch --show-current` so you're working against current code.

## Code Style & Design

- Prefer simple, minimal, idiomatic solutions. Do not propose abstractions, wrappers, or architectural patterns beyond what is explicitly requested. When in doubt, ask before adding complexity.

<!-- System-dependency gating (package installs + remote/history git ops) is enforced by the PreToolUse hook hooks/block_dangerous_commands.py, registered via settings.shared.json. It prompts for confirmation rather than running these automatically — even in bypass-permissions mode. -->

## Debugging

When debugging or investigating issues, present your hypothesis and the evidence for it. Do NOT assert a root cause unless you can prove it with code or data. If the user disproves a hypothesis, move on to a genuinely different angle.

## Git & Commits

- Always use the `/commit` slash command for commits — it scopes to the files from our conversation and handles the message format and atomic staging. Do NOT run `git commit` directly.
- Never add a `Co-Authored-By` line or any AI-attribution trailer to commit messages.
- For commit messages, use the EXACT wording the user provides if given. If no message is provided, use your best judgment to write one — do not ask.
- Don't run remote git operations (`push`, `pull`, `fetch`, `rebase`) unless the user explicitly asks.

## Agent Delegation

Prefer **agent teams** over subagents for substantive parallel work — teammates share a task list, message each other directly, and coordinate without going through the lead. Strongest use cases:

- **Research and review**: teammates investigate different aspects simultaneously, then share and challenge each other's findings
- **New modules or features**: teammates each own a separate piece without stepping on each other
- **Debugging with competing hypotheses**: teammates test different theories in parallel and converge faster
- **Cross-layer coordination**: changes spanning frontend, backend, and tests, each owned by a different teammate

Use subagents (Agent tool) only for quick, focused tasks where only the result matters and workers don't need to communicate. Use the main session only for coordination and final synthesis.

Best practices: 3–5 teammates. Give each teammate task-specific context in the spawn prompt (they don't inherit the lead's history). Break work so teammates own different files to avoid conflicts.

## Implementation Plans

For any substantial code change NOT using plan mode, write the implementation plan to a scratch file before starting work — e.g. `./tmp/<short-topic>-plan.md`. The file should capture the goal, the files to touch, and the step-by-step approach. This preserves context across auto-compaction. Delete the file when the work is complete and verified. "Substantial" = multi-file changes, anything requiring sequencing, or work that will span more than a few tool calls. Trivial edits (typo fixes, single-line changes, one-off questions) do not need a plan file.

## Running Scripts

- NEVER run a script as a blocking foreground call — it locks the session until it finishes. Always run scripts in the background so I can watch progress and stay available for other questions.
- Default: launch the script with background Bash (`run_in_background: true`). When I ask "how's it going?", poll the task's accumulated output and report progress — without stopping it.
- When the output needs interpreting (parsing logs, detecting errors/stalls, summarizing long runs), launch a **background subagent** (`Agent` with `run_in_background: true`) to run and monitor the script, and report progress on request. Reserve an **agent team** for scripts that fan out into genuinely independent long-running pieces — otherwise a single background task/subagent is simpler. Tell me which you chose and why.
- The invariant: a running script must never block me from asking other things, and I must be able to surface its progress on demand without interrupting it.

## Temporary Files & Scripts

- Analysis scripts, one-off queries, and other short-lived scripts go to `/tmp` by default — do NOT persist them in the repo unless explicitly asked.
- If a task spans multiple days (e.g. a plan file or a script you'll need tomorrow), use `./tmp/` instead — it's project-scoped and survives reboots. Add `./tmp/` to `.gitignore` if it isn't already.
- `./tmp/` is an exception to any rule against reading gitignored files: even though it is gitignored, always read plan files and scripts in `./tmp/` when they are relevant to the current task.
- Only write a script to the repo root (or another permanent location) when the user explicitly asks to keep it.

## Machine-Local Instructions

<!-- Per-machine instructions live in ~/.claude/CLAUDE.local.md (untracked — mirrors the ~/.zshrc.local pattern; absent on machines with no local overrides). -->

@~/.claude/CLAUDE.local.md

## Tests

- Before modifying any code, run the relevant tests to establish a baseline. If tests are already failing before your change, report that to the user before proceeding.
- When adding new code (new functions, classes, modules, features), add corresponding tests in the same change. Follow the project's existing test conventions and location.
- When modifying existing code, run the relevant tests after the change and report the result. If the project has no tests for the touched area, say so explicitly rather than skipping silently.
- If the test command isn't obvious from the project, ask before guessing.

## Code Search Strategy

Searching is really context-budget management: every search result and every file you open to disambiguate a hit consumes context, and your effectiveness degrades as it fills. So prefer whichever tool reaches certainty about where code lives for the fewest tokens — the one that returns a handful of precise hits, not hundreds of noisy lines you then have to open files to sort out. Narrow before you widen.

- **Prefer structural over textual for code shape.** For definitions, call sites, subclasses, decorator usages, or specific argument shapes, prefer `ast-grep` in any language with a tree-sitter grammar — it matches the syntax tree, so it skips comments and string literals and avoids regex false positives. Fall back to ripgrep for genuinely textual targets: config values, log strings, comments, cross-language sweeps.
- **Use ripgrep deliberately, not as bare `grep -r`.** Before a non-trivial search, introspect the tool (`rg --help`, or `rg --type-list` to see available language filters) and pick the flags that most narrow the result set up front rather than filtering output by hand afterward. Reach for: `-t`/`--type` to scope by language, `-g` globs to scope by path, `-w` for whole-word, `-l` for filenames-only when you just need locations, `-A`/`-B`/`-C` for surrounding context, `-o` to print only matches. If a search returns an unwieldy number of hits, that's the signal to add a scope flag and re-run, not to start opening files.
- **Glob to scope, then search within.** Narrow by path/type first (`rg -g '**/<area>/**' -t py <pattern>`) instead of searching the whole tree and discarding most of it.
- **Follow the symbol; don't re-scan.** Once you've located a definition, trace behavior by reading its imports and call sites rather than re-running the same search repeatedly.
- **Delegate broad exploration to a subagent.** For open-ended "where/how is X handled across the codebase" questions, hand the searching to a subagent so the file-reading happens in its context and only the summary returns to the main session — this is the single biggest lever for keeping the main context clean.
- **Use the repo's own map first.** When a project's CLAUDE.md documents structure, entrypoints, or registration points, jump there before searching blind — agentic search works best when you already know roughly where to look.
