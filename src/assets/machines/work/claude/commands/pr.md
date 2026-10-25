---
description: Run a parallel multi-agent PR review and produce paste-ready Bitbucket change requests
allowed-tools: Bash(git log:*), Bash(git diff:*), Bash(git branch:*), Bash(git status:*), Bash(git checkout:*), Bash(git for-each-ref:*), Read, Grep, Glob, Agent, SendMessage
---

## Instructions

Run a full parallel review of a PR and produce paste-ready Bitbucket change requests.

We use **Bitbucket, not GitHub** — `gh` and any GitHub PR tooling are unavailable and irrelevant. The PR exists only as a git branch.

### Step 1 — Locate the PR

1. If the user named a branch, use it. Otherwise find the likeliest candidate from recently-updated branches (`git for-each-ref --sort=-committerdate refs/heads/ --format='%(refname:short) %(committerdate:relative)'`) and confirm with the user before proceeding.
2. Determine the diff base: `production` unless the repo's CLAUDE.md or branch layout says otherwise.
3. Understand the PR before reviewing:
   - `git log <base>..<branch>` — intent, from commit messages
   - `git diff <base>...<branch> --stat` — scope and changed-file list
4. If the branch isn't checked out in the current worktree: first record the restore target (`git branch --show-current`, or the HEAD SHA if already detached — after detaching, `git branch --show-current` returns empty), then detach onto the PR tip (`git checkout --detach <branch>`) so reviewers can read the PR code on disk. The final output must end with how to restore (`git checkout <restore-target>`).

### Step 2 — Fan out three parallel review agents

Launch three general-purpose subagents **in a single message** so they run concurrently. Give each a distinct name (`correctness`, `security`, `simplify`) so they are addressable later. All three are **report-only — they must not edit files.**

Each agent prompt must be fully self-contained (subagents inherit nothing from this session). Every prompt gets a context header:

- The working directory; the base and PR branch names; the exact diff command: `git diff <base>...<branch>`
- The changed-file list from Step 1
- Relevant repo context summarized from the repo's CLAUDE.md (architecture, idioms, test conventions)
- The instruction that they are report-only and must not modify any file
- Findings return with severity, `file:line`, the issue, a concrete failure scenario, and the recommended change — except where the embedded body below specifies its own output format, which then takes precedence. Always include explicit "clean" statements for each area checked (so silence is distinguishable from "not examined").

After the header, each prompt embeds its review body below **verbatim** — these are lifted from the built-in `/code-review`, `/security-review`, and `/simplify` skills; do not paraphrase, trim, or reorder them. Lines in [square brackets] are the only local adaptations (Bitbucket branch diff instead of GitHub/working tree; report instead of fix).

**If an agent goes idle without delivering findings** (this happens), request the findings via `SendMessage` to that agent by name — do not respawn it.

#### Correctness agent — the /code-review correctness angles

[Adaptation: the diff under review is `git diff <base>...<branch>`. Additionally, verify each commit-message claim from `git log <base>..<branch>` is actually implemented in the diff — a claimed behavior with no corresponding code is a finding.]

Run the **5 correctness angles below as independent finder sub-agents** via the Agent tool, all in a single message so they run concurrently. Each surfaces up to 8 candidate findings with `file`, `line`, a one-line `summary`, and a concrete `failure_scenario`. Do NOT let one angle's conclusions suppress another's — if two angles flag the same line for different reasons, record both.

### Angle A — line-by-line diff scan

Read every hunk in the diff, line by line. Then Read the enclosing function for
each hunk — bugs in unchanged lines of a touched function are in scope (the PR
re-exposes or fails to fix them). For every line ask: what input, state, timing,
or platform makes this line wrong? Look for inverted/wrong conditions,
off-by-one, null/undefined deref, missing `await`, falsy-zero checks,
wrong-variable copy-paste, error swallowed in catch, unescaped regex metachars.

### Angle B — removed-behavior auditor

For every line the diff DELETES or replaces, name the invariant or behavior it
enforced, then search the new code for where that invariant is re-established.
If you can't find it, that's a candidate: a removed guard, a dropped error
path, a narrowed validation, a deleted test that was covering a real case.

### Angle C — cross-file tracer

For each function the diff changes, find its callers (Grep for the symbol) and
check whether the change breaks any call site: a new precondition, a changed
return shape, a new exception, a timing/ordering dependency. Also check callees:
does a parallel change in the same PR make a call unsafe?

### Angle D — language-pitfall specialist

Scan for the classic pitfalls of the diff's language/framework — for example:
JS falsy-zero, `==` coercion, closure-captured loop var; Python mutable default
args, late-binding closures; Go nil-map write, range-var capture; SQL injection;
timezone/DST drift; float equality. Flag any instance the diff introduces.

### Angle E — wrapper/proxy correctness

When the PR adds or modifies a type that wraps another (cache, proxy, decorator,
adapter): check that every method routes to the wrapped instance and not back
through a registry/session/global — e.g. a caching provider holding a
`delegate` field that resolves IDs via `session.get(...)` instead of
`delegate.get(...)` will re-enter the cache or recurse. Also check that the
wrapper forwards all the methods the callers actually use.

Pass every candidate with a nameable failure scenario through — finders that
silently drop half-believed candidates bypass the verify step and are the
dominant cause of misses.

#### Security agent — the /security-review prompt

[Adaptations: the changes under review are the branch diff — gather context by running `git status`, `git diff --name-only <base>...<branch>`, `git log --no-decorate <base>..<branch>`, and `git diff <base>...<branch>` instead of the `origin/HEAD...` commands. "PR" means the Bitbucket branch under review. In this codebase, PHI (patient identifiers, phone numbers, DOB) counts as PII/sensitive data throughout.]

You are a senior security engineer conducting a focused security review of the changes on this branch.

Review the complete diff. This contains all code changes in the PR.

OBJECTIVE:
Perform a security-focused code review to identify HIGH-CONFIDENCE security vulnerabilities that could have real exploitation potential. This is not a general code review - focus ONLY on security implications newly added by this PR. Do not comment on existing security concerns.

CRITICAL INSTRUCTIONS:
1. MINIMIZE FALSE POSITIVES: Only flag issues where you're >80% confident of actual exploitability
2. AVOID NOISE: Skip theoretical issues, style concerns, or low-impact findings
3. FOCUS ON IMPACT: Prioritize vulnerabilities that could lead to unauthorized access, data breaches, or system compromise
4. EXCLUSIONS: Do NOT report the following issue types:
   - Denial of Service (DOS) vulnerabilities, even if they allow service disruption
   - Secrets or sensitive data stored on disk (these are handled by other processes)
   - Rate limiting or resource exhaustion issues

SECURITY CATEGORIES TO EXAMINE:

**Input Validation Vulnerabilities:**
- SQL injection via unsanitized user input
- Command injection in system calls or subprocesses
- XXE injection in XML parsing
- Template injection in templating engines
- NoSQL injection in database queries
- Path traversal in file operations

**Authentication & Authorization Issues:**
- Authentication bypass logic
- Privilege escalation paths
- Session management flaws
- JWT token vulnerabilities
- Authorization logic bypasses

**Crypto & Secrets Management:**
- Hardcoded API keys, passwords, or tokens
- Weak cryptographic algorithms or implementations
- Improper key storage or management
- Cryptographic randomness issues
- Certificate validation bypasses

**Injection & Code Execution:**
- Remote code execution via deserialization
- Pickle injection in Python
- YAML deserialization vulnerabilities
- Eval injection in dynamic code execution
- XSS vulnerabilities in web applications (reflected, stored, DOM-based)

**Data Exposure:**
- Sensitive data logging or storage
- PII handling violations
- API endpoint data leakage
- Debug information exposure

Additional notes:
- Even if something is only exploitable from the local network, it can still be a HIGH severity issue

ANALYSIS METHODOLOGY:

Phase 1 - Repository Context Research (Use file search tools):
- Identify existing security frameworks and libraries in use
- Look for established secure coding patterns in the codebase
- Examine existing sanitization and validation patterns
- Understand the project's security model and threat model

Phase 2 - Comparative Analysis:
- Compare new code changes against existing security patterns
- Identify deviations from established secure practices
- Look for inconsistent security implementations
- Flag code that introduces new attack surfaces

Phase 3 - Vulnerability Assessment:
- Examine each modified file for security implications
- Trace data flow from user inputs to sensitive operations
- Look for privilege boundaries being crossed unsafely
- Identify injection points and unsafe deserialization

REQUIRED OUTPUT FORMAT:

You MUST output your findings in markdown. The markdown output should contain the file, line number, severity, category (e.g. `sql_injection` or `xss`), description, exploit scenario, and fix recommendation.

For example:

# Vuln 1: XSS: `foo.py:42`

* Severity: High
* Description: User input from `username` parameter is directly interpolated into HTML without escaping, allowing reflected XSS attacks
* Exploit Scenario: Attacker crafts URL like /bar?q=<script>alert(document.cookie)</script> to execute JavaScript in victim's browser, enabling session hijacking or data theft
* Recommendation: Use Flask's escape() function or Jinja2 templates with auto-escaping enabled for all user inputs rendered in HTML

SEVERITY GUIDELINES:
- **HIGH**: Directly exploitable vulnerabilities leading to RCE, data breach, or authentication bypass
- **MEDIUM**: Vulnerabilities requiring specific conditions but with significant impact
- **LOW**: Defense-in-depth issues or lower-impact vulnerabilities

CONFIDENCE SCORING:
- 0.9-1.0: Certain exploit path identified, tested if possible
- 0.8-0.9: Clear vulnerability pattern with known exploitation methods
- 0.7-0.8: Suspicious pattern requiring specific conditions to exploit
- Below 0.7: Don't report (too speculative)

FINAL REMINDER:
Focus on HIGH and MEDIUM findings only. Better to miss some theoretical issues than flood the report with false positives. Each finding should be something a security engineer would confidently raise in a PR review.

FALSE POSITIVE FILTERING:

> You do not need to run commands to reproduce the vulnerability, just read the code to determine if it is a real vulnerability. Do not use the bash tool or write to any files.
>
> HARD EXCLUSIONS - Automatically exclude findings matching these patterns:
> 1. Denial of Service (DOS) vulnerabilities or resource exhaustion attacks.
> 2. Secrets or credentials stored on disk if they are otherwise secured.
> 3. Rate limiting concerns or service overload scenarios.
> 4. Memory consumption or CPU exhaustion issues.
> 5. Lack of input validation on non-security-critical fields without proven security impact.
> 6. Input sanitization concerns for CI workflows unless they are clearly triggerable via untrusted input.
> 7. A lack of hardening measures. Code is not expected to implement all security best practices, only flag concrete vulnerabilities.
> 8. Race conditions or timing attacks that are theoretical rather than practical issues. Only report a race condition if it is concretely problematic.
> 9. Vulnerabilities related to outdated third-party libraries. These are managed separately and should not be reported here.
> 10. Memory safety issues such as buffer overflows or use-after-free vulnerabilities are impossible in rust. Do not report memory safety issues in rust or any other memory safe languages.
> 11. Files that are only unit tests or only used as part of running tests.
> 12. Log spoofing concerns. Outputting un-sanitized user input to logs is not a vulnerability.
> 13. SSRF vulnerabilities that only control the path. SSRF is only a concern if it can control the host or protocol.
> 14. Including user-controlled content in AI system prompts is not a vulnerability.
> 15. Regex injection. Injecting untrusted content into a regex is not a vulnerability.
> 16. Regex DOS concerns.
> 17. Insecure documentation. Do not report any findings in documentation files such as markdown files.
> 18. A lack of audit logs is not a vulnerability.
>
> PRECEDENTS -
> 1. Logging high value secrets in plaintext is a vulnerability. Logging URLs is assumed to be safe.
> 2. UUIDs can be assumed to be unguessable and do not need to be validated.
> 3. Environment variables and CLI flags are trusted values. Attackers are generally not able to modify them in a secure environment. Any attack that relies on controlling an environment variable is invalid.
> 4. Resource management issues such as memory or file descriptor leaks are not valid.
> 5. Subtle or low impact web vulnerabilities such as tabnabbing, XS-Leaks, prototype pollution, and open redirects should not be reported unless they are extremely high confidence.
> 6. React and Angular are generally secure against XSS. These frameworks do not need to sanitize or escape user input unless it is using dangerouslySetInnerHTML, bypassSecurityTrustHtml, or similar methods. Do not report XSS vulnerabilities in React or Angular components or tsx files unless they are using unsafe methods.
> 7. Most vulnerabilities in CI workflows are not exploitable in practice. Before validating a CI workflow vulnerability ensure it is concrete and has a very specific attack path.
> 8. A lack of permission checking or authentication in client-side JS/TS code is not a vulnerability. Client-side code is not trusted and does not need to implement these checks, they are handled on the server-side. The same applies to all flows that send untrusted data to the backend, the backend is responsible for validating and sanitizing all inputs.
> 9. Only include MEDIUM findings if they are obvious and concrete issues.
> 10. Most vulnerabilities in ipython notebooks (*.ipynb files) are not exploitable in practice. Before validating a notebook vulnerability ensure it is concrete and has a very specific attack path where untrusted input can trigger the vulnerability.
> 11. Logging non-PII data is not a vulnerability even if the data may be sensitive. Only report logging vulnerabilities if they expose sensitive information such as secrets, passwords, or personally identifiable information (PII).
> 12. Command injection vulnerabilities in shell scripts are generally not exploitable in practice since shell scripts generally do not run with untrusted user input. Only report command injection vulnerabilities in shell scripts if they are concrete and have a very specific attack path for untrusted input.
>
> SIGNAL QUALITY CRITERIA - For remaining findings, assess:
> 1. Is there a concrete, exploitable vulnerability with a clear attack path?
> 2. Does this represent a real security risk vs theoretical best practice?
> 3. Are there specific code locations and reproduction steps?
> 4. Would this finding be actionable for a security team?
>
> For each finding, assign a confidence score from 1-10:
> - 1-3: Low confidence, likely false positive or noise
> - 4-6: Medium confidence, needs investigation
> - 7-10: High confidence, likely true vulnerability

START ANALYSIS:

Begin your analysis now. Do this in 3 steps:

1. Use a sub-task to identify vulnerabilities. Use the repository exploration tools to understand the codebase context, then analyze the PR changes for security implications. In the prompt for this sub-task, include all of the above.
2. Then for each vulnerability identified by the above sub-task, create a new sub-task to filter out false-positives. Launch these sub-tasks as parallel sub-tasks. In the prompt for these sub-tasks, include everything in the "FALSE POSITIVE FILTERING" instructions.
3. Filter out any vulnerabilities where the sub-task reported a confidence less than 8.

Your final reply must contain the markdown report and nothing else.

#### Simplification agent — the /simplify review phase

[Adaptations: the diff under review is `git diff <base>...<branch>`; report-only — /simplify's "apply the fixes" phase is replaced by reporting the findings.]

You are improving the quality of the changed code, not hunting for bugs. Review
it for reuse, simplification, efficiency, and altitude issues, then report what you
find. Do not look for correctness bugs — that is what the correctness reviewer is for.

Launch **4 independent review agents** via the Agent tool, all in a
single message so they run concurrently. Pass each agent the diff and one of
the four angles below. Each returns its findings with `file`, `line`, a
one-line `summary`, and the concrete cost (what is duplicated, wasted, or
harder to maintain).

### Reuse

Flag new code that re-implements something the codebase
already has — Grep shared/utility modules and files adjacent to the change,
and name the existing helper to call instead.

### Simplification

Flag unnecessary complexity the diff adds: redundant or derivable state,
copy-paste with slight variation, deep nesting, dead code left behind. Name
the simpler form that does the same job.

### Efficiency

Flag wasted work the diff introduces: redundant computation or repeated I/O,
independent operations run sequentially, blocking work added to startup or
hot paths. Also flag long-lived objects built from closures or captured
environments — they keep the entire enclosing scope alive for the object's
lifetime (a memory leak when that scope holds large values); prefer a
class/struct that copies only the fields it needs. Name the cheaper
alternative.

### Altitude

Check that each change is implemented at the right depth, not as a fragile
bandaid. Special cases layered on shared infrastructure are a sign the fix
isn't deep enough — prefer generalizing the underlying mechanism over adding
special cases.

Wait for all four agents to complete, dedup findings that point at the same
line or mechanism, and report each remaining one. Skip any finding whose
fix would change intended behavior, require changes well outside the reviewed
diff, or that you judge to be a false positive — note the skip rather than
arguing with it.

### Step 3 — Synthesize

Merge the three reports into one rank-ordered change-request list:

- Order by real-world impact: patient/data-integrity issues first, then crashes, then lint/dead code, then quality suggestions, then nits.
- Deduplicate overlapping findings across reviewers (keep the strongest framing; credit the concrete failure scenario).
- Label each item **request changes**, **non-blocking**, or **nit**.
- **Scale the published list to the PR's size.** The finder stages stay exhaustive, but the published output is calibrated: as a guide, up to ~5 findings for a small diff (< ~300 changed lines), up to ~8 for a medium one, and 10–15 only for a genuinely large PR (thousands of lines). Confirmed request-changes items always make the cut; trim non-blocking items first and nits hardest (batch surviving nits into a single finding). Close with one sentence naming the themes that were cut so the author can ask for the full list.

**Verify before publishing (the /code-review verify pass).** Dedup candidates that point at the same line/mechanism, keeping the one with the most concrete failure scenario. For each remaining candidate, run **one verifier** via the Agent tool: give it the diff, the relevant file(s), and the candidate, and have it return exactly one of:

- **CONFIRMED** — can name the inputs/state that trigger it and the wrong
  output or crash. Quote the line.
- **PLAUSIBLE** — mechanism is real, trigger is uncertain (timing, env,
  config). State what would confirm it.
- **REFUTED** — factually wrong (code doesn't say that) or guarded elsewhere.
  Quote the line that proves it.

**PLAUSIBLE by default** — do not refute a candidate for being "speculative" or
"depends on runtime state" when the state is realistic: concurrency races,
nil/undefined on a rare-but-reachable path (error handler, cold cache, missing
optional field), falsy-zero treated as missing, off-by-one on a boundary the
code does not exclude, retry storms / partial failures, regex/allowlist that
lost an anchor. These are PLAUSIBLE.

**REFUTED** only when constructible from the code: factually wrong (quote the
actual line); provably impossible (type/constant/invariant — show it); already
handled in this diff (cite the guard); or pure style with no observable effect.

Drop REFUTED findings entirely. A finding labeled **request changes** must be CONFIRMED; a PLAUSIBLE finding publishes as **non-blocking** at most.

### Step 4 — Output format (most important)

Each finding is paste-ready for a Bitbucket comment thread and has exactly three parts. **Never use blockquotes (`>`)** for the paste-ready text — terminal rendering adds `▎` pipe markers that pollute a copy-paste. Put the comment and the example fix prompt each in a fenced `text` code block instead, so a terminal copy grabs clean text.

1. **Anchor line** (outside any fence): bold `N. path/to/file.py line NNN` (path in backticks), then ` — request changes` (or non-blocking / nit). See the worked example below for the exact shape.

2. **PR comment** (fenced text block): built to skim. The **first sentence states the problem in plain words** — what actually goes wrong and for whom, no line numbers or symbol names unless essential ("A cancelled surgery can be un-cancelled by a merge and submitted as performed", not "merge_cancellation_status combines flags with AND"). Then 2–4 tight sentences: the concrete failure scenario, why it's the common case (if it is), and what a change would achieve. Short enough to read at a glance — deep detail (line citations, traced values, edge conditions) belongs in the example fix prompt, not here. **Phrased entirely without imperatives or directives** — never "do X", "please X", or "you should X". Use conditional/observational phrasing: "normalizing before comparing closes the casing variants", "keying the groupby on a stable subset removes that failure mode", "wrapping the read in try/except makes both cases behave the same".

3. **Example fix prompt** (fenced text block, introduced with the literal label `Example fix prompt:` — the "example" respects the author's judgment and context): a prompt the PR author can hand verbatim to an agent. Self-contained: file, approximate line, symbol names, the defect in one sentence. Then the fixed behavior described as an end state ("Fixed behavior: …", "Fixed state: …") rather than as commands. Ends with a "Done means …" sentence naming the **exact test file path** and a **concrete existing test module as the style exemplar** (found by looking at the repo's test tree — e.g. "tests in testing/client_tests/test_foo.py, style of test_bar.py, with the repo's usual mocks"), plus the exact verification commands to pass. Hedged phrasing like "per existing conventions" is not acceptable — the author shouldn't have to do that lookup. Also no imperatives.

Worked example of one finding (generic — adapt content, keep the shape exactly):

**1. `pipeline/consent.py` line 84** — request changes

```text
Opted-out patients can silently stay active. Anything other than the exact literal
"Opt Out" — "opt out", "OptOut", trailing space, "Declined" — is treated as consent, and
the schema doesn't constrain the field, so a feed-format drift fails open with no signal.
Normalizing before comparing (strip + casefold) closes the casing/whitespace variants, and
a warning on unrecognized values surfaces a wording drift in logs instead. The feed spec
is the authority on the actual token spelling.
```

Example fix prompt:

```text
In pipeline/consent.py ConsentProcessor.process (~line 84), the guard
`if value != "Opt Out": return record` fails open on any variant of the opt-out token.
Fixed behavior: the value is normalized via (value or "").strip().casefold() and matched
against "opt out"; blank/None remains a no-op; a non-blank value outside the recognized
set produces a logger.warning (no identifiers in the message) rather than silent
pass-through. Done means tests exist in tests/test_consent.py covering "Opt Out",
"opt out", "OptOut ", blank, None, and "Declined", and `uv run pytest
tests/test_consent.py` passes.
```

End the full output with the restore note from Step 1 (e.g. `git checkout <restore-target>`) if the worktree was detached.
