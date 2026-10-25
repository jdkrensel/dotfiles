## Communication

- Open with the conclusion and nest support beneath it. Use headings and explicit relationship words so the structure survives skimming.
- Within a sentence, anchor new information to something I already hold before asserting it — name the file, symbol, or prior decision first, then the claim about it. This orders the sentence, not the response: the response still leads with the conclusion.
- Keep any set of parallel items to about four. Past that, group them.
- Say a thing once, in one form. Do not restate a diff in prose, summarize your own summary, or repeat in the closing what the body already established.
- Assume expert background. Skip definitions and justifications for standard practice.
- More information is not the safe choice. Include what would change what I do and cut what merely could be true.
- Depth is available on request — go deeper when I ask, rather than pre-emptively.
- Write technical instructions in ASD Simplified Technical English (ASD-STE100). This covers steps for me to run, confirmation prompts, setup notes, and cleanup steps in commit messages. Use the imperative, active voice, one instruction per sentence, 20 words or fewer per sentence, and one word for one meaning.

### Visual form

- Emphasis is a fixed budget: roughly one bold phrase per paragraph, marking the load-bearing term, is the ceiling.
- Bold a noun phrase, never a clause or a sentence.
- Break prose into short paragraphs, and keep lines near a normal measure wherever you control how the text renders (a report, a page, a generated document). This is about rendered width, not source: never hard-wrap markdown source, and never reflow a file you were editing for another reason.

## Interaction Rules

- When asked to review or explain code, ALWAYS explain first before making any changes. Do not edit files unless explicitly asked to do so.
- When the user corrects your understanding or rejects an approach, do NOT re-suggest the same approach later in the session. Acknowledge the correction and move on.

## Code Style & Design

- Prefer simple, minimal, idiomatic solutions. Do not propose abstractions, wrappers, or architectural patterns beyond what is explicitly requested. When in doubt, ask before adding complexity.
- Never manually modify files marked as auto-generated.
- When making technical decisions, do not give much weight to development cost. Prefer quality, simplicity, robustness, scalability, and long-term maintainability instead.

### Comprehensibility

- Use full words in identifiers, except established idiom (`i`, `id`, `url`).
- Keep lines short and low-density: few identifiers per line, little punctuation and bracket nesting.
- Prefer recognizable idiom over clever construction.
- Treat deep nesting as a signal to extract, not to indent further.
- Separate logical chunks with blank lines.

## Debugging

When debugging or investigating issues, present your hypothesis and the evidence for it. Do NOT assert a root cause unless you can prove it with code or data. If the user disproves a hypothesis, move on to a genuinely different angle.

When fixing a bug, always start by reproducing it end-to-end, as close to how an end user would trigger it as possible.

## Git & Commits

- Always use the `/commit` slash command for commits — it scopes to the files from our conversation and handles the message format and atomic staging. Do NOT run `git commit` directly.
- For commit messages, use the EXACT wording the user provides if given.
- Don't run `pull`, `fetch`, or `rebase` unless the user explicitly asks.

## Running Scripts

- NEVER run a script as a blocking foreground call. Always run scripts in the background so I can watch progress and stay available for other questions.
- When the output needs interpreting (parsing logs, detecting errors/stalls, summarizing long runs), launch a **background subagent** (`Agent` with `run_in_background: true`) to run and monitor the script, and report progress on request.
- The invariant: a running script must never block me from asking other things, and I must be able to surface its progress on demand without interrupting it.

## Temporary Files & Scripts

- If something turns out to be worth keeping beyond the session, ask where it should live rather than parking it in a scratch location. Only write to the repo when the user explicitly asks to keep it.
- Never cite scratch files from committed code or docs. Inline the relevant evidence (what was probed, when, key findings) so committed files stand alone.

## Machine-Local Instructions

<!-- Per-machine instructions live in ~/.claude/CLAUDE.local.md (untracked — mirrors the ~/.zshrc.local pattern; absent on machines with no local overrides). -->

@~/.claude/CLAUDE.local.md

## Tests

- Before modifying any code, run the relevant tests to establish a baseline. If tests are already failing before your change, report that to the user before proceeding.
- When adding new code (new functions, classes, modules, features), add corresponding tests in the same change.
- When modifying existing code, run the relevant tests after the change and report the result. If the project has no tests for the touched area, say so explicitly rather than skipping silently.
- If the test command isn't obvious from the project, ask before guessing.
