# Independent card check

Your own checks run in the same context that wrote the card, so you already know the answer and read the front through it. That's why giveaway cues, two-option fronts, and fronts that state their own fact slip past you. This check hands the card to an agent that knows nothing about how it was written.

## How to run it

Spawn one subagent per batch (Agent tool, general-purpose). Give it only the prompt below with the cards filled in — no conversation history, sources, or reasoning. Wait for its verdicts.

- **Pass:** present the card.
- **Fail:** fix the specific problem once, then re-check just that card in a new subagent. If it fails again, drop it and list it as dropped.

A failure usually means the framing is wrong, not the fact, so the one fix should change the card's shape rather than polish its wording. For a two-option or give-away failure, flip the direction: instead of "which X solves this?" (where X has only two values, or the scenario names it), ask what X does or adds — "What does hybrid search add to semantic-only retrieval?" → keyword matching on the chunk text. Rewording the same shape almost always fails the same way.

If you can't spawn subagents, run the two passes yourself in order, answering each front before you let yourself look at its intended answer, and treat any doubt as a fail.

## Prompt

```
You are checking flashcards before a learner adds them. You have not seen how they were written. Work in two passes, in order.

PASS 1 — answer blind. Below are only the fronts. For each, write the answer a knowledgeable person in this subject would most likely give. Do not look ahead.

<numbered fronts only>

PASS 2 — try to break each card. Now compare with the intended answers:

<numbered front → intended answer pairs>

For each card, report FAIL with a one-line reason if any of these hold, otherwise PASS:
1. Your pass-1 answer differs from the intended answer but is also correct, or another answer an expert would give is also correct.
2. Someone with no knowledge of the subject could get the answer from the wording alone — a word or phrase that points to it, the front restating the answer, or a cue that narrows it to one obvious choice.
3. The question offers (or implies) only two options and one is clearly eliminable, so it tests elimination rather than knowledge.
4. The front states the fact the card is meant to test, leaving nothing to retrieve.
5. The front can't be answered without knowing where it came from (an unnamed article, "this service", an undefined term).

Reply as a numbered list: PASS, or FAIL — <reason>. Nothing else.
```
