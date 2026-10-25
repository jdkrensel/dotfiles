# Domain profile: AWS and the AIP-C01 exam

Read this when a card or question is about AWS services or the AWS Certified Generative AI Developer – Professional (AIP-C01) exam. It adds to the core rules in `SKILL.md`; it never relaxes them.

The full official exam outline (all 98 skill IDs, verbatim) is in `exam-guide.md` in this folder. Search it for the skill a card belongs to rather than reading it whole.

## Contents

1. Exam scope and weights
2. Verifying facts (mandatory)
3. The AWS Decision note type
4. Deck and tags
5. Decision-card patterns and recurring distractor traps
6. Exam-style questions, question sets, and leeches
7. Worked examples

---

## 1. Exam scope and weights

65 scored + 10 unscored questions, multiple choice and multiple response, scaled 100–1,000, pass at 750, compensatory scoring.

| Domain | Name | Weight |
|---|---|---|
| D1 | Foundation Model Integration, Data Management, and Compliance | 31% |
| D2 | Implementation and Integration | 26% |
| D3 | AI Safety, Security, and Governance | 20% |
| D4 | Operational Efficiency and Optimization for GenAI Applications | 12% |
| D5 | Testing, Validation, and Troubleshooting | 11% |

The exam tests judgment: which service or pattern fits a situation, and why the plausible alternative doesn't. Model development, training internals, advanced ML techniques and feature engineering are explicitly out of scope — a card about them is T0 for this deck.

Before carding a service, check it's in scope: `exam-guide.md` lists in-scope and out-of-scope services in its appendix. An out-of-scope service can still appear as a distractor, so a card on it is fine if it teaches why it's the wrong choice.

## 2. Verifying facts (mandatory)

AWS changes constantly, and model memory of it is stale and confidently wrong. For this domain, verification isn't conditional: every card's answer must be backed by current official documentation, including when you're reviewing a card the user wrote.

1. **Fetch the source** from docs.aws.amazon.com. Many pages have a Markdown version: append `.md` to the HTML URL, which is cheaper to read. Prefer user guides and API references over blog posts and marketing pages.
2. **Quote the supporting sentence** verbatim in the Source field, with the URL.
3. **Stamp the date** in the Verified field as YYYY-MM-DD.
4. **If you can't find a supporting sentence, don't ship it.** Report the card as unverified and say what you tried. If two official pages conflict, say so, go with the newer page, and tag the card `volatile`.
5. **The Source field must stand on its own.** Before presenting, go through every factual claim on the card — the Answer, each claim in Why and WhyNot, and any premise the front relies on (e.g. "without purchasing capacity") — and point to the quoted sentence in this card's Source that supports it. A claim being true, or supported by a sentence you read but didn't quote, isn't enough. Quote the missing sentence, or cut the claim.

   The same bar applies to everything else in your reply, especially the verdict line. Never tell the user their answer is wrong or narrower than they think unless a quoted sentence says so — and read the whole page first, since a page often covers the same feature under more than one error or heading.
6. **Tag volatile facts** — quotas, region availability, supported-store or supported-connector lists, preview or recently launched features — with `volatile` so they get re-checked.

## 3. The AWS Decision note type

Default note type for this deck. Fields, in order:

| Field | Shown | Content |
|---|---|---|
| Scenario | Front | The question or scenario, with a context cue like `[Bedrock KB · ingestion]` |
| Answer | Back | The one correct answer, as short as possible |
| Why | Back | One or two sentences: the reason this is the answer. Fill it on every card. |
| WhyNot | Back | The tempting distractor and why it's wrong. Fill it whenever a plausible distractor exists. |
| Source | Back, small | URL and quoted sentence |
| Verified | Back, small | YYYY-MM-DD |
| SkillID | Back, small | e.g. `1.4.2` |

Only Scenario → Answer is the retrieval. Why and WhyNot are elaboration read after answering; keep them short. Use the built-in Basic type for plain facts that don't fit a decision shape, with the source and date on the back, and Cloze only for a fixed, ordered list.

The `<b>…</b>` grading line goes in the Answer field and nowhere else. Answer is already the minimum, so the bolded span is usually the whole field: `<b>Step Functions</b>`. Never bold text in Why or WhyNot. The template's bold **Why:** and **Why not:** labels are headings, not the grading line.

If the note type doesn't exist yet, create it with `create_model`:

```json
{
  "model_name": "AWS Decision",
  "in_order_fields": ["Scenario", "Answer", "Why", "WhyNot", "Source", "Verified", "SkillID"],
  "card_templates": [{
    "Name": "Decision",
    "Front": "{{Scenario}}",
    "Back": "{{FrontSide}}<hr id=answer>{{Answer}}{{#Why}}<br><br><b>Why:</b> {{Why}}{{/Why}}{{#WhyNot}}<br><b>Why not:</b> {{WhyNot}}{{/WhyNot}}<div class=meta>{{Source}}<br>verified {{Verified}} · {{SkillID}}</div>"
  }],
  "css": ".card { font-family: -apple-system, sans-serif; font-size: 20px; text-align: left; line-height: 1.4; max-width: 40em; margin: 0 auto; } .meta { margin-top: 1.5em; font-size: 13px; opacity: 0.6; }"
}
```

## 4. Deck and tags

- **Deck:** `AIP-C01`, one deck for everything, so the scheduler interleaves topics. Interleaving similar categories is what trains discrimination between near-twin services; separately studied subdecks throw that away.
- **Tags** on every note:
  - `aip::<skill id>`, e.g. `aip::1.4.2`.
  - `src::aws-docs`, `src::sample-question`, or `src::hands-on`.
  - `volatile` for facts likely to change.

**Choosing the skill ID.** Don't guess from memory. Search `exam-guide.md` for the service and the action the card tests, then pick the skill whose wording covers both. When two skills fit, prefer the one whose verb matches the card: *design / select* for choice cards, *troubleshoot* for failure cards, *implement* for configuration cards. If it's still a tie, pick the skill whose example services include the card's answer. Always commit to exactly one ID; don't present the choice to the user unless they ask.

When suggesting what to card next, budget by domain weight. Per skill, plan 0–2 foundation cards (only for services new to the user), 2–4 decision cards, and 1 contrast or why-not card.

## 5. Decision-card patterns

Each pattern stays atomic: one deciding constraint per card.

- **Scenario → choice.** The scenario contains the one constraint that makes a single answer correct among *all* realistic options. Ask openly ("Which vector store must you use?"), and check with the alternative-answer test that nothing else qualifies.
- **Signature constraint ("the tell").** The reverse direction: the service → the workload feature that points to it.
- **Why-not.** A near-miss distractor and the reason it fails.
- **Pairwise contrast.** Two named services and one deciding property. Use "A or B?" only when A and B are genuine near-twins that get confused in practice, like contextual grounding vs. Automated Reasoning checks, or on-demand vs. Provisioned Throughput. If the open question would have several valid answers, add a constraint to the scenario instead of narrowing it to two options — a two-option front over services nobody confuses tests elimination, not knowledge.
- **Principle card.** For the big A-vs-B-vs-C choices (prompt engineering vs. RAG vs. fine-tuning; agents vs. Step Functions), write one card per trigger, not one per comparison.

### Recurring distractor patterns

AIP-C01 distractors are built from a handful of traps. When carding an exam-style question, name the trap its most tempting wrong option uses — the card should teach the trap's tell, not just this question's answer.

| Trap | What it looks like | Card that defuses it |
|---|---|---|
| **Custom build vs. built-in feature** | A Lambda proxy, custom scoring, or hand-rolled workflow next to a managed feature that does the same job. Under "LEAST operational overhead" the built-in feature wins. | Signature card for the built-in feature: "Which Bedrock feature does X without custom code?" |
| **Right family, wrong layer** | Several logging or monitoring services that each capture a different thing: CloudTrail records API metadata (who called what, when), model invocation logging records prompt and response content, knowledge base logging records per-document ingestion status. | Contrast card per pair: "Which one captures <the specific thing>?" |
| **Instruction instead of mechanism** | Asking the model in the prompt to stop, redact, or obey a rule, next to a parameter or service that enforces it (stop sequences, Comprehend PII redaction, guardrails). | Why-not card: "Why is a prompt instruction the wrong way to <requirement>?" → the model may not comply; enforcement needs a mechanism. |
| **One keyword flips the answer** | A requirement word that eliminates otherwise-good options: "peak periods" vs. steady load, "same FM", "infrequent queries", "immediate" vs. "resilient". The same service can be right in one question and wrong in the next — SQS is wrong when feedback must be immediate (polling adds latency) and right when the pipeline must buffer and retry. | Scenario → choice card whose front contains that keyword, plus a contrast card when the same service flips. |
| **Hard limit decides** | A number in the scenario (payload size, processing time, dataset size) that only one option's limit accommodates. | One card per decisive limit, tagged `volatile` and verified against current docs — practice explanations quote limits that drift. |

Anki trains cue → decision. It doesn't train weighing three or four stacked constraints against distractors; say so if the user asks what cards can't cover.

## 6. Exam-style questions, question sets, and leeches

**Exam-style question.** The user shares a scenario question with its correct answer and the reasoning for each option. Treat it purely as reference material for what's correct; the card is about the AWS knowledge, never about the question or anyone's attempt at it. Produce at most:

1. A decision card for the deciding constraint — the requirement that makes the correct answer correct.
2. A why-not card for the most tempting wrong option, naming the trap from the table in section 5 if one applies.

Don't card the whole question — it stacks constraints and won't stay atomic. Tag `src::sample-question`. Verify both cards against docs; the explanations in question sets are sometimes wrong or out of date, and their quoted limits drift.

Adapt by question type:

- **Multi-select:** each correct option is its own decision target, and each tempting wrong option is a why-not target. That can be four or more targets — rank them by how broadly the underlying fact applies, card the top two, and list the rest for later rather than producing them all at once.
- **Ordering:** card the steps whose order is non-obvious, as "what must happen before/after X, and why" — not the whole sequence.

**A whole question set.** When the user hands over many questions at once, don't card everything — that's weeks of new-card budget. Rank the questions by domain weight and by how often the same trap recurs across them, propose the top handful with one line each (question number, the deciding fact, the card it would become), and let the user choose which to draft first.

**Leech or high-lapse card.** Diagnose before rewriting: which of the five criteria is failing? Usual fixes are splitting it, adding a context cue, or adding a contrast card for the twin it's confused with. If the user keeps forgetting the answer rather than misreading the question, suggest they rewrite the answer in their own words.

## 7. Worked examples

These illustrate form. Verify any fact before reusing it on a real card.

**Focused**
- ✓ [Bedrock Guardrails] Which API applies your configured guardrails to text without invoking a foundation model? → ApplyGuardrail.
- ✗ Explain Bedrock Guardrails. (Many answers; a different subset each time.)

**One answer**
- ✓ [Bedrock Guardrails] Which safeguard flags model responses that aren't supported by the retrieved source? → Contextual grounding check.
- ✗ How does Bedrock reduce hallucinations? (Contextual grounding, Automated Reasoning, RAG and prompt engineering are all valid.)

**No sets**
- ✗ List the vector stores Bedrock Knowledge Bases supports.
- ✓ One decision card per store, keyed to the situation that selects it: [Bedrock KB · data sources] Your knowledge base ingests from Confluence via the built-in connector. Which vector store must you use? → Amazon OpenSearch Serverless.

**Contrast between genuine near-twins**
- ✓ Contextual grounding check vs. Automated Reasoning check — which validates a response against logical rules you define? → Automated Reasoning.

**Not binary**
- ✗ Can Bedrock Guardrails be used with non-Bedrock models?
- ✓ How do you apply Bedrock Guardrails to a model hosted outside Bedrock? → Call ApplyGuardrail on its inputs and outputs.

**Principle**
- ✓ A multi-step process must follow the same auditable path every time, with retries. Bedrock Agents or Step Functions? → Step Functions (an agent is for when the model should choose the steps).
