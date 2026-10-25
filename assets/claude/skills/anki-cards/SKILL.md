---
name: anki-cards
description: Review, shape, and write Anki flashcards to a strict quality bar, then add approved cards to Anki through the AnkiMCP server. Use this skill whenever the user pastes a question/answer and asks if it's a good flashcard, describes a card they want to make, asks you to improve, rate, or critique a card, or asks you to draft cards from a topic, a document, an exam-style question, or a leech. Use it even when they don't say "Anki" — "is this a good card?", "help me make a card for X", or "turn this into flashcards" all count.
---

# Anki cards

The user adds only a few new cards a day, so every card has to earn its slot. A card is a recurring task the user's future self will perform for years. A bad card costs minutes of review and erodes neighbouring memories, so fewer, better cards always beat more.

The usual flow is that the user brings a card idea — often a question and answer written in their own habitual style — and you help make sure it's actually a good card. You can also draft cards from scratch when asked. Both share one quality standard, below.

## Domain profiles

Some subjects have a profile that adds domain rules: where facts must be verified, which note type, deck and tags to use, and card patterns for that domain. Read a profile only when the card or question is about its subject. When no profile matches, this file is complete on its own — don't load a profile "just in case".

| Profile | Read it when |
|---|---|
| `domains/aws/PROFILE.md` | The card or question is about AWS services or the AWS AIP-C01 certification exam |

A profile adds to the rules here; it never relaxes them.

`references/principles.md` has the full rule set, exact rubric definitions, and worked examples. Read it when a verdict is borderline or you need to cite the precise rule.

## The quality standard

### Tiers

Grade every card on the Memory Machines scale (Kirkby & Matuschak, 2026). The tier is decided by the **question/front**; the answer may carry extra detail.

| Tier | Name | Meaning | What to do |
|---|---|---|---|
| T3 | Ready to Review | Specific, unambiguous, will cue the same retrieval every time | Ship |
| T2 | Needs Polish | Sound targeting and construction; minor wording fixes | Fix the wording, then ship |
| T1 | Needs Refactor | Right region of meaning but unreliable in review — looks plausible, degrades over months | Restructure (split, rescope, add context) or kill |
| T0 | Off-target | Asks about the wrong thing — trivia, or not what the user cares about | Kill or retarget |

T1 is the worst outcome, worse than T0, because it looks fine at approval time and only fails months into review. The study's cost weights are T0 −1, T1 −3, T2 +1.5, T3 +2. Only T3 cards are presented as finished.

### The five failure criteria

1. **Lacks context** — the front can't be answered in isolation, six months from now, without the source in hand ("according to the article…", "this tool", an undefined term).
2. **Solicits multiple responses** — two competent people, or the same person months apart, could give different valid answers. Red flags: "main/key/primary", "an effective way", "why is X important", vague "how", broad scope.
3. **Wordy** — phrasing longer or fancier than the retrieval needs.
4. **Shallow** — tests a label, count or name whose loss wouldn't reduce understanding; or the answer is a vague generalization.
5. **Narrow** — tests example scaffolding or a literal metaphor instead of the conceptual core.

### Checks that need procedure, not judgment

LLMs reliably catch "lacks context". They are poor at "multiple responses" (judge F1 ≈ 0.32–0.50) and terrible at "wordy" (F1 ≈ 0.07–0.37), and they pick structurally broken T1 cards a third of the time when choosing among candidates. Your sense that a card "looks fine" is therefore not evidence. Run these procedures and show their results:

- **Alternative-answer test (multiple responses).** Write down the two strongest *different* answers a knowledgeable person could plausibly give to the front as worded — the answers an expert would actually reach for, not easy ones to dismiss. If the alternatives you came up with are obviously wrong, you haven't tested the card yet; look harder. If either is also correct, the card fails — add the constraint that rules it out, or split the card.
- **Cut test (wordy).** Try deleting each word or phrase on the front. If the deletion doesn't change which answer is correct, delete it. Fronts should almost never exceed 25 words; scenario fronts can run longer only when every clause is a constraint the answer depends on.
- **Six-month test (lacks context).** Read the front as if you'd forgotten the source, the deck and this conversation. Every term must be either defined by the card's context cue or common in the domain.
- **Give-away test (effortful).** Could someone answer from the wording alone, with no knowledge of the topic? If so, the cue is too strong.
- **Binary test.** Yes/no and this-or-that fronts produce shallow understanding. Rephrase to ask *how*, *which*, or *what*. The exception is a contrast card naming two genuine near-twins — things the learner actually confuses — and asking which one has a specific property.

When a check finds a problem you can name, fix it before presenting. A card with a known, fixable flaw is at most T2, whatever else is right about it — so fix it, don't label it. Mention a risk only when it's genuine uncertainty you can't resolve.

### Design rules

- One retrieval per card. Split compound questions; each half becomes its own card.
- No sets or open lists. Turn a list into one card per item, each attached to the situation that selects it. A fixed, ordered list may use one cloze per item.
- Prefer question–answer over cloze. Cloze copied from a source invites pattern matching.
- Put a short context cue on the front, like `[git · rebase]`, to separate near-twins without giving the answer away.
- Write "why" and contrast cards alongside fact cards. Approach important ideas from two or three angles so the idea isn't a lonely orphan — but respect the low daily budget by choosing the angles that matter most.
- Put mnemonics and elaboration on the back, never on the front.
- Bold the grading line. On the back, wrap in `<b>…</b>` only the minimum the learner must say for the card to count as correct — never elaboration, examples, mnemonics, sources or "why" notes. Use exactly one bolded span; if the required part can't be one span, the card asks for more than one retrieval, so split it. The bold must match what the front asks: if a correct answer to the front could leave out the bolded text, fix the front or the bold.
- Answer in one plain sentence. Open the back with one complete sentence that restates the front's subject and answers it, with the bolded span inside it. Name the subject in full; don't open with "it" or "this" in its place. Use few commas and no stacked clauses. If the front's wording forces a clunky restatement, reword the front, then run the checks and the independent check on it again. Put elaboration, examples and mnemonics on their own lines after that sentence.
- Chart growth-rate cards. When a card is about how a quantity grows with its input — big O rungs, doubling or halving, comparing growth rates — put an inline SVG chart on the back that shows the card's own claim. Never chart other cards, such as a definition, and never put a chart on the front, where it gives the answer away. Build it with `scripts/growth_chart.py`; its docstring has the chart rules.
- Only card material the user has already learned. If they haven't studied the topic yet, say so and suggest reading or building first.

### Facts must be right

A well-formed card with a wrong answer is worse than no card. When an answer depends on a fact that changes over time, is contested, or that you aren't certain of, verify it against an authoritative source and put the source on the card. If you can't verify it, say so rather than presenting it as settled. A domain profile may make verification mandatory and name the sources.

## Reviewing the user's card idea

This is the main mode. The user may bring a finished question and answer, a rough one, or just a description of what they want to remember. Your job is to help *their* idea become a good card, not to replace it with yours.

1. **Pin the target** — what the card should make them recall. If their question actually tests something different from what they said they wanted, that's the first finding.
2. **Verify the answer** if it's a fact that could be wrong (see "Facts must be right"). A wrong answer outranks every style issue; lead with it.
3. **Run every check**, then make the smallest edit that fixes what fails, keeping their wording, format and style wherever those aren't the cause. If the card needs splitting, produce each resulting card.
4. **Run the independent check** in `references/checker.md` on every card you're about to present, including a card of theirs you'd pass unchanged.
5. **Present the result**, per the format below.

The checks are your working, not the deliverable. The user wants a good card, not the case for it: show the card and the briefest reason it changed, and keep the full reasoning for when they ask "why?".

If the card is already T3, say so in one line and stop — don't invent problems. Suggest at most one companion card if it would genuinely help.

If they only described an idea, draft one or two phrasings in the style of cards they've shown you and present them the same way.

If a call is genuinely borderline — wordy vs. fine, or whether a second answer is "really" valid — say so in one line and let the user decide.

### Review format

Keep it short and easy to scan. The revised card comes first; everything else is one line.

```
**T1 → edit before adding.** Your front also accepts "<strongest alt answer>".

**Front:** <revised>
**Back:** <one sentence that names the subject in full, with **<required part>** inside it>
<elaboration, on its own line>
<further fields, if the note type has them>

Add it, tweak it, or drop it?
```

- The line after the verdict names the main failure in the user's terms — usually the strongest alternative answer, since that's the flaw they're least likely to see. One line, not a list of criteria.
- Don't show original → revised side by side, a checks line, word counts, or advice about the user's habits unless they ask.
- For a split, show each card under its own **Card N** label with no commentary between them.
- In reviews and drafts, show the bold as Anki will render it, in markdown bold, not as literal `<b>…</b>` tags. The tags still go into the Anki field and to the checker in `references/checker.md`.

## Drafting cards from scratch

1. **Pin the target.** Identify the one thing the user should be able to retrieve or decide. If the request is broad, propose the 2–5 most valuable targets and let the user choose rather than carpet-bombing the topic.
2. **Look before you write.** If the Anki MCP tools are available, search the target deck for existing cards on the topic. Avoid duplicates, and note near-twins that call for a contrast card.
3. **Get the facts right** per the section above and any matching profile. A card you can't verify doesn't ship — report it instead.
4. **Draft more than you need, then cut.** Draft two or three phrasings per target, run every check on each, keep the best. Drop anything still T1 or worse after one rewrite; say what you dropped and why.
5. **Run the independent check** in `references/checker.md` on the batch you're about to present.
6. **Present for approval**, then stop and wait.

### Draft format

```
**Card 1 — <short target>**
**Front:** …
**Back:** <one sentence that names the subject in full, with **…** inside it>
<elaboration, on its own line>
<any further fields the note type defines>
Chart: <preview path, for a growth-rate card>
Source: <where the fact was verified, if it needed verifying>
```

For a growth-rate card, draft the chart with the card: write it with `--preview` to a temp file (your scratchpad, or `$TMPDIR`) and `open` the page, so the user approves both together. Present only cards that passed every check; don't print the checks. After the cards, list anything you dropped or couldn't verify, one line each. End by asking which cards to add, edit, or kill. If the user rewrites an answer in their own words, keep their phrasing — paraphrasing what you study measurably helps retention (Pan et al.).

## Adding to Anki

Add only cards the user has approved, exactly as approved, including their edits and the `<b>…</b>` around the required part. "Add it" in reply to a review or draft counts as approval. Put an approved chart's SVG at the end of the Back field, after the answer sentence and elaboration, separated by `<br><br>`. Follow `references/anki-mcp.md`, and use the note type, deck and tags from the matching profile if there is one; otherwise ask which deck to use. Report the note IDs and anything skipped as a duplicate, and offer to sync.
