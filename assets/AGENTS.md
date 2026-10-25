## Communication

- Write technical instructions in ASD Simplified Technical English (ASD-STE100). This covers steps for me to run, confirmation prompts, setup notes, and cleanup steps in commit messages. Use the imperative, active voice, one instruction per sentence, 20 words or fewer per sentence, and one word for one meaning.

## Interaction Rules

- Edit files only when I ask for a change. A request to review, explain, or investigate is not permission to edit. Repro scripts and scratch files outside the repo are not edits.

## Debugging

Reproduce or trace every issue end-to-end before you conclude anything about it. When fixing a bug, reproduce it as close to how an end user would trigger it as possible. After the fix, run the same reproduction or re-trace to confirm it no longer fails. When an issue has multiple edge cases, reproduce or trace each one separately. One confirmed case does not confirm the others.

Verify every premise a conclusion depends on before you use it. Check the claim against code, data, logs, or a run. A premise that sounds plausible is not verified.

If verification needs access you do not have, such as logs, AWS, a database, Google Docs, Asana, or Slack, stop and ask for it. Do not continue on an unverified premise in place of that access.

With each debugging conclusion, state any assumption that would change the conclusion if it were false.

## Git & Commits

- Always use the `/commit` slash command for commits — it scopes to the files from our conversation and handles the message format and atomic staging. Do NOT run `git commit` directly.
- For commit messages, use the EXACT wording the user provides if given.
- Don't run `pull`, `fetch`, or `rebase` unless the user explicitly asks.

## Files

- Never cite scratch files from committed code or docs. Inline the relevant evidence (what was probed, when, key findings) so committed files stand alone.
- Never edit generated files by hand, including files marked as auto-generated and lockfiles. Regenerate them with the tool that produces them.

## Machine-Local Instructions

<!-- Per-machine instructions live in ~/.claude/CLAUDE.local.md (untracked — mirrors the ~/.zshrc.local pattern; absent on machines with no local overrides). -->

@~/.claude/CLAUDE.local.md

## Tests

- Before modifying any code, run the relevant tests to establish a baseline. If tests related to your change are already failing, report that to the user and wait for a reply. Mention failures in unrelated tests in one line, then proceed.
- After modifying code, run the relevant tests and report the result. If the touched area has no tests, say so.
- When adding new code (new functions, classes, modules, features), add corresponding tests in the same change.
- Refactor only code that has tests. A refactor is any change that keeps behavior the same, including organization changes: moving or renaming files, and renaming functions. If the code has no tests, add them and commit them with `/commit` before you refactor. After the refactor, run them to confirm the behavior did not change. For files that cannot carry tests, such as config, shell rc files, and markdown, find every reference to the file instead.
- If the test command isn't obvious from the project, ask before guessing.

## Refactoring: separate shape changes from behavior changes

Keep non-behavioral changes (anything that changes the code's shape but not what it does) separate from behavioral changes, and land the non-behavioral ones first. Ideally they ship on their own, so the behavioral change is reviewed against code that already has its final shape and the reviewer only sees what actually changed.

Non-behavioral changes include moving or splitting files, renaming files and symbols, and refactors like extracting functions. A task might involve any combination of these, or none. Use only the ones the task needs, but when several apply, give each its own commit (moves before renames) so each diff stays easy to skim.

### Moving files
Always move or split files with `git mv`. Never create a new file and delete the old one; when splitting, `git mv` the original to the piece that keeps most of its content, and only the split-off pieces are new files. Git detects renames by content similarity, so a move combined with edits shows up as a delete + add and loses history. In a move commit, only make the edits needed to keep things working (import paths, re-exports). Before committing, check that `git diff --cached -M --name-status` shows renames (`R`), not delete + add pairs.

### Example: module → package
`utils.py` needs to become `utils/` with `parsing.py` and `io.py`:
- `git mv utils.py utils/parsing.py` (history follows the largest chunk), move the I/O functions into `utils/io.py` verbatim, and add `utils/__init__.py` re-exporting the public names so existing imports still work. Commit.
- If names also need to change, rename them in a following commit.
- The behavior change comes after, ideally in its own PR.
