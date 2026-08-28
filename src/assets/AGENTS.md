## Communication

<!-- Grounded in: Cowan 2001 (WM ~4 chunks); Sweller (redundancy effect); Kalyuga (expertise reversal); Jacoby 1974 / Shields 1983 / Iselin 1988 (overload inverted-U); Clark & Haviland (given-new); Meyer (signaling). -->

- Open with the conclusion and nest support beneath it. Use headings and explicit relationship words so the structure survives skimming.
- Within a sentence, anchor new information to something I already hold before asserting it — name the file, symbol, or prior decision first, then the claim about it. This orders the sentence, not the response: the response still leads with the conclusion.
- Keep any set of parallel items to about four. Past that, group them — an ungrouped list of nine is a list I will skim, not read.
- Say a thing once, in one form. Do not restate a diff in prose, summarize your own summary, or repeat in the closing what the body already established.
- Assume expert background. Skip definitions, justifications for standard practice, and "here's what I'm about to do" preambles.
- More information is not the safe choice. Past a threshold it degrades my decisions rather than improving them, so include what would change what I do and cut what merely could be true.
- Report outcomes, not a step-by-step trace of your own actions. Depth is available on request — go deeper when I ask, rather than pre-emptively.

### Visual form

<!-- Grounded in: Kwantes & Vandeberg 2025 (uniform bolding costs vs. plain text); Dunlosky 2013 (highlighting rated low utility; over-application destroys it); Taylor et al. 2020 (disfluency does not aid retention); Bringhurst / Dyson & Haselgrove (line length). -->

- Emphasis is a fixed budget spent against itself. Bold works by differing from its surroundings, so each bold phrase devalues every other one — roughly one per paragraph, marking the load-bearing term, is the ceiling.
- Bold a noun phrase, never a clause or a sentence. Uniformly heavier text measurably slows reading compared to plain text; it does not speed it up.
- Break prose into short paragraphs, and keep lines near a normal measure wherever you control how the text renders (a report, a page, a generated document). Very long and very short lines both disrupt eye movement. This is about rendered width, not source: never hard-wrap markdown source, and never reflow a file you were editing for another reason.
- Never trade legibility for visual interest. Making text harder to process does not aid retention — that effect failed to replicate.

## Interaction Rules

- When asked to review or explain code, ALWAYS explain first before making any changes. Do not edit files unless explicitly asked to do so.
- When the user corrects your understanding or rejects an approach, do NOT re-suggest the same approach later in the session. Acknowledge the correction and move on.
- Before reviewing or editing, re-read the relevant files from disk rather than relying on earlier reads, and confirm the working branch with `git branch --show-current` so you're working against current code.

## Code Style & Design

- Prefer simple, minimal, idiomatic solutions. Do not propose abstractions, wrappers, or architectural patterns beyond what is explicitly requested. When in doubt, ask before adding complexity.
- Never manually modify files marked as auto-generated.
- When making technical decisions, do not give much weight to development cost. Prefer quality, simplicity, robustness, scalability, and long-term maintainability instead.

### Comprehensibility

<!-- Grounded in: Hofmeister et al. (words vs. abbreviations, 19% faster defect location); Buse & Weimer (readability model); Siegmund et al. (beacons, fMRI); Peitek et al. ICSE 2021 (complexity metrics are weak comprehension proxies). -->

- Use full words in identifiers. Single letters and abbreviations measurably slow readers, and abbreviating buys nothing over a single letter — expand unless the short form is established domain idiom (`i`, `id`, `url`).
- Keep lines short and low-density. Line length, identifiers per line, and punctuation/bracket density are the strongest negative predictors of readability — stronger than logical complexity.
- Prefer recognizable idiom over clever construction. Readers pattern-match familiar shapes and only fall back to tracing logic when the shape is unfamiliar, so novelty costs them real effort.
- Do not optimize for cyclomatic complexity. It is a weak proxy for comprehension effort; size, vocabulary, and naming track it better.
- Follow the project's indentation. Where genuinely unconstrained, 2-4 spaces reads best and deeper indentation adds nothing — so treat deep nesting as a signal to extract, not to indent further.
- Separate logical chunks with blank lines. Readers segment code into functional units before reasoning about it, and blank lines are what mark the boundaries.

<!-- System-dependency gating (package installs + remote/history git ops) is enforced by the PreToolUse hook hooks/block_dangerous_commands.py, registered via settings.shared.json. It prompts for confirmation rather than running these automatically — even in bypass-permissions mode. -->

## Debugging

When debugging or investigating issues, present your hypothesis and the evidence for it. Do NOT assert a root cause unless you can prove it with code or data. If the user disproves a hypothesis, move on to a genuinely different angle.

When fixing a bug, always start by reproducing it end-to-end, as close to how an end user would trigger it as possible. This surfaces the real problem so the fix actually resolves it, rather than patching a symptom guessed at from reading code.

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

## Running Scripts

- NEVER run a script as a blocking foreground call — it locks the session until it finishes. Always run scripts in the background so I can watch progress and stay available for other questions.
- Default: launch the script with background Bash (`run_in_background: true`). When I ask "how's it going?", poll the task's accumulated output and report progress — without stopping it.
- When the output needs interpreting (parsing logs, detecting errors/stalls, summarizing long runs), launch a **background subagent** (`Agent` with `run_in_background: true`) to run and monitor the script, and report progress on request. Reserve an **agent team** for scripts that fan out into genuinely independent long-running pieces — otherwise a single background task/subagent is simpler. Tell me which you chose and why.
- The invariant: a running script must never block me from asking other things, and I must be able to surface its progress on demand without interrupting it.

## Temporary Files & Scripts

- Anything temporary — analysis scripts, one-off queries, intermediate outputs — goes in the session scratchpad directory, never the repo.
- If something turns out to be worth keeping beyond the session, ask where it should live rather than parking it in a scratch location. Only write to the repo when the user explicitly asks to keep it.
- Never cite scratch files from committed code or docs. Inline the relevant evidence (what was probed, when, key findings) so committed files stand alone.

## Machine-Local Instructions

<!-- Per-machine instructions live in ~/.claude/CLAUDE.local.md (untracked — mirrors the ~/.zshrc.local pattern; absent on machines with no local overrides). -->

@~/.claude/CLAUDE.local.md

## Tests

- Run tests via a **subagent** (Agent tool), not inline Bash — test output is verbose and burns main-session context. The subagent runs the suite and returns only a summary: pass/fail counts and, on failure, the failing test names with the relevant error output. Exception: a single narrow test in a tight debug loop, where you need the raw output immediately, may run inline.
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
