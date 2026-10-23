# Card-design principles: full reference

Verified against primary sources on 2026-10-19. Read the section you need:

1. Memory Machines rubric — tiers, decision rules, the five failure criteria
2. Matuschak's five properties and his guidance by card type
3. Wozniak's twenty rules
4. Nielsen's heuristics
5. Worked examples (good card vs. near-miss)

---

## 1. Memory Machines rubric (Kirkby & Matuschak, 2026)

Sources: https://memory-machines.com/report; the judge prompts quoted below are from https://github.com/laddermedia/memory-machines (`memory_machines/probes/instructions/`, `tiering/instructions/rate_ungrounded.txt`).

The study scores prompts on two axes:

- **Meaningful (targeting):** the prompt "captures details the user genuinely cares about long-term, not trivialities."
- **Stable (construction):** the prompt "can be consistently retrieved from memory even after months, when reviewed in isolation without access to the original context."

### Tiers

| Tier | Name | Judge-prompt definition |
|---|---|---|
| T3 | Ready to Review | "can be used as-is… specific, unambiguous, and will consistently trigger the same retrieval pathway." |
| T2 | Needs Polish | Reviewable; core targeting and construction sound; "would benefit from minor tweaks to wording, phrasing, or context." |
| T1 | Needs Refactor | "roughly in the right region of meaning but… ineffective for review… requires substantial restructuring." Typical causes: soliciting multiple valid responses, missing context cues, too wordy, lacking depth. |
| T0 | Off-target | Targets the wrong information: a different aspect entirely, or nearby details the user doesn't care about. May be well constructed. |

Decision rules from the judge prompt:

- The T1/T2 gap "represents the threshold of reviewability."
- "Focus on the Question, Not the Answer." Answers may carry extra detail.
- Generic or definitional questions ("what is X?", "what is the key principle of X?") are "often too vague" — usually T1.
- Gap analysis decides the tier: only minor wording changes needed → T2; a structural change (splitting a compound prompt, changing scope) → T1; wrong recall target → T0.

### The five failure criteria (verbatim definitions)

**1. Lacks context.** "the QUESTION cannot be answered in isolation without referring back to the source text." If the question raises "'which article?' or 'according to whom?'", it is ambiguous. Causes: vague source references ("According to the article…"), undefined or metaphorical terms, deictic "this/that/the system". Distinct from being overly broad.
- Example: "What does excise involve?" → "What is excise according to Alan Cooper?"

**2. Solicits multiple responses.** "can be answered in multiple ways… if two users might provide different answers even after reading the same source text, or if the same user reviewing months later might recall a different valid answer." Red flags: subjective qualifiers ("primary/main/key/fundamental"), indefinite articles ("What is **an** effective strategy…"), "why is X important/critical", overly broad questions, vague "how" questions. Rescued by attribution to a specific person or framework, definite articles, or a stated count ("the three benefits").

**3. Wordy.** "uses unnecessarily complex phrasing or verbose constructions that obscure clarity… primarily about how something is said." Patterns: formal qualifiers ("pivotal agreement"), passive or indirect voice, fancy vocabulary ("delineates"), redundant double-asks, over-explained context. Necessary technical terms are not wordy.
- Example: "How does the Stoic philosophy, as summarized by Marcus Aurelius, view obstacles in relation to personal growth and progress?" → "How does Marcus Aurelius's Stoic philosophy view obstacles?"

**4. Shallow.** "tests surface-level information rather than meaningful understanding." A good prompt "isolates one meaningful detail… exposing structure, causality, relationships, or principles." Fails either as a shallow question (counts, labels, names, locations without significance) or a shallow answer (vague generalization, a "what" answer to a "how/why" question). Test: "A detail is trivial if forgetting it wouldn't reduce comprehension." But "Sometimes specificity IS the depth."

**5. Narrow.** "focuses on the wrong aspect of the highlight—testing surface details, example scaffolding, or literal metaphor elements while missing the conceptual core." Patterns: testing the literal metaphor instead of the principle, the mechanism instead of the claim, example trivia, a platitude stripped of its application.

### What the study found about LLM judges (why the skill uses procedures)

- Best-model judging accuracy on usable vs. unusable: 67% (Opus 4.5, few-shot). No model exceeded 70%.
- Opus 4.5 picked a T1 prompt in 32.6% of comparisons even when a T3 was present.
- Per-criterion judge F1: lacks context 0.85–0.87 (frontier models); narrow 0.55–0.74; shallow 0.57–0.72; multiple responses 0.32–0.50; wordy 0.07–0.37.
- Judges are "best at judging criteria that are apparent without review: missing context, surface ambiguity, shallow phrasing" and "weakest at… clarity and answer stability."
- Grounding the judge with human-rated examples for the same material cut false positives from 52% to 17%.
- Asking for "literal, context-free" trivia-style questions produced 75% unusable output.

---

## 2. Matuschak — "How to write good prompts" (December 2020)

Source: https://andymatuschak.org/prompts/

### The five properties

| Property | Core definition |
|---|---|
| Focused | "It's usually best to focus on one detail at a time." Too much detail "will dull your concentration and stimulate incomplete retrievals." |
| Precise | "Vague questions will elicit vague answers." |
| Consistent | "should produce consistent answers, lighting the same bulbs each time." Otherwise retrieval-induced forgetting inhibits the related details you didn't recall. |
| Tractable | "write prompts which you can almost always answer correctly. This often means breaking the task down, or adding cues." |
| Effortful | "You shouldn't be able to trivially infer the answer. Cues are helpful… just don't 'give the answer away.'" |

"Achieving these properties is mostly about writing tightly-scoped questions."

### Guidance by card type

**Simple facts.** Decompose. "What do you need to make chicken stock?" fails several properties at once; "What type of chicken parts are used in stock?" → "Bones" doesn't.

**Explanation prompts.** "Explanations make facts more meaningful." They must still be precise: "Why do we use bones…?" admits "because they're cheap"; "How do bones produce a chicken stock's rich texture?" → "They're full of gelatin" doesn't. Attribute claims you can't verify ("Why does Andy's recipe claim…").

**Closed lists.** One prompt per element, list in a fixed order, one blank per review, so you learn the list's "shape". Add a why-prompt per element where it matters.

**Open lists.** Cloze doesn't work ("anything could reasonably go in that first slot"). Treat the list as a tag: instance → tag, a prompt about the tag's pattern, and at most a fuzzy "name two…" prompt backed by other cards.

**Cues.** "??? (herb)" is a good cue; "??? (rhymes with parrots)" is bad — "You could answer this without having ever read the recipe."

**Cloze vs. Q&A.** "Cloze deletions seem particularly susceptible to [pattern matching], especially when created by copying and editing passages from texts." Prefer short Q&A.

**Binary prompts.** "Questions which ask for a yes/no or this/that answer tend to require little effort and produce shallow understanding." Fix by connecting to an example or implication: "Does stock make vegetables taste like chicken?" → "How does chicken stock affect the flavor of vegetable dishes?"

**Context.** "You must include enough context that reasonable alternative answers are clearly wrong, while not including so much context that you encourage pattern matching or dilute the question's focus." General knowledge should be expressed generally, not tied to one source.

**Volume.** "Write more prompts than feels natural" — an easy prompt costs 10–30 seconds in its first year. Counterweight: fewer prompts for material you already know well.

**Concepts.** Trace a concept's edges with five lenses: attributes and tendencies; similarities and differences; parts and wholes; causes and effects; significance and implications. Definition-only prompts ("What is X?") let you parrot.

**Procedures.** Strip each step to its keywords; prompt on the conditions for moving between steps; add heads-up prompts ("takes about an hour").

**Maintenance.** Notice an internal "sigh" during review — that's a prompt to fix.

---

## 3. Wozniak — "Twenty rules of formulating knowledge" (1999)

Source: https://www.super-memory.com/articles/20rules.htm. Listed in order of importance.

1. Do not learn if you do not understand
2. Learn before you memorize — "build the picture of the whole before you dismember it into simple items"
3. Build upon the basics
4. Stick to the minimum information principle
5. Cloze deletion is easy and effective
6. Use imagery
7. Use mnemonic techniques
8. Graphic deletion is as good as cloze deletion
9. Avoid sets — "Sets are unacceptable!"
10. Avoid enumerations
11. Combat interference — "probably the single greatest cause of forgetting"
12. Optimize wording
13. Refer to other memories
14. Personalize and provide examples
15. Rely on emotional states
16. Context cues simplify wording
17. Redundancy does not contradict the minimum information principle
18. Provide sources
19. Provide date stamping
20. Prioritize

---

## 4. Nielsen — "Augmenting Long-term Memory" (2018)

Source: http://augmentingcognition.com/ltm.html

- **Atomicity:** "Make most Anki questions and answers as atomic as possible." One card he routinely got wrong became two he routinely got right. Atomic doesn't mean low-level — it's relative to background knowledge.
- **Budget:** 15–20 minutes of review a day; if it "routinely rises to much more than 20 minutes it usually means I'm adding cards too rapidly."
- **No orphans:** "never put in one question… at least two questions in, preferably three or more."
- **Yes/no is a "question smell"** — refactor into which-case, example, or meaning questions.
- **Both directions:** ask paper → claim and claim → paper; they're different triggers.

---

## 5. Worked examples

**Focused**
- ✓ Front: [git] Which command moves your branch's commits onto the tip of another branch, rewriting their history? → `git rebase`.
- ✗ Front: Explain git rebase. (Many answers; a different subset each time.)

**One answer**
- ✓ Front: [cell biology] Which organelle produces most of a cell's ATP? → The mitochondrion.
- ✗ Front: How does a cell get energy? (Glycolysis, respiration, fermentation, photosynthesis are all valid.)

**No sets**
- ✗ Front: List the causes of World War I.
- ✓ One card per cause, each asking what that cause contributed ("Which 1914 assassination triggered Austria-Hungary's ultimatum to Serbia?").

**Contrast to fight interference**
- ✓ Front: [git] `merge` vs. `rebase` — which preserves the original commit history unchanged? → `merge`.

**Not binary**
- ✗ Front: Does `git rebase` rewrite history?
- ✓ Front: [git] Why shouldn't you rebase commits already pushed to a shared branch? → It rewrites their hashes, so collaborators' history diverges.

**Why prompt**
- ✓ Front: [cooking] How do bones give chicken stock its rich texture? → They release gelatin.
