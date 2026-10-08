# Method: Crosby's evals approach, applied to Margin (MLR pre-review)

## Sources found

**Primary source:** Aveek Duttagupta, "How we do evals at Crosby," Crosby blog, October 6, 2026. https://crosby.ai/blog/how-we-do-evals-at-crosby. Read in full on 2026-10-07. Crosby is an AI-powered law firm doing contract review.

**Secondary:** the owner's internal notes mapping the post onto MLR review (private; not included in this template). Where any notes differ from the post, the post wins.

**Searched with no match:** the owner's internal repos and notes had no additional Crosby material.

## What the post says

Crosby uses three principles, quoted from the post:

1. **"Verifying deterministically wherever possible."** Break evaluation into discrete, checkable units. Their examples: did the edit land on the targeted paragraph, was it the most surgical edit, is the comment attached to the right text, was an undefined term introduced.
   - Deterministic checks are "the first line in our evaluation system that establishes that the output is structurally valid before we attempt to evaluate its legal quality."
   - The same output gives the same result every time. Checks catch regressions; one fix "quietly introduced 40 malformed comments, and our checks caught it before it shipped."
2. **"Evaluating judgment through real comparisons."** Use pairwise preference instead of 1–10 scores or rubric-heavy golden sets: "Which of these two redlines would you rather send to the client?"
   - Comparisons are blind and the order is randomized.
   - Reviewers also mark separately "whether they would actually send the version as written." Preference alone does not mean the output is good enough.
   - The data engine is the agent draft paired with the lawyer-final version.
   - Each gap is labeled as either a synthesis failure (the agent had the information) or missing context (e.g., verbal preferences from a call).
   - Judges are sanity-checked on pairs with a known winner: a stronger model should beat a weaker one, and the correct playbook should beat a removed or wrong one. "If a judge can't get these obvious cases right, it isn't ready to evaluate closer calls."
3. **"Building a shared system around the actual work."** Experts label in a workbench that looks like their tool (Word). They adjust context inputs, not prompts.

Reported results:
- Two attorneys agreed on 45% of 500 edits.
- Reviews up to 5x faster.
- Review time fell 74% for NDAs and about 80% for MSAs, in controlled trials over about 2 months covering about 1,000 edits in 30 contracts.

## How Margin applies it

| Crosby | Margin (this repo) |
|---|---|
| Deterministic structural checks first | `checks/`: regex, presence and proximity checks over the piece text plus metadata. Examples: established name next to brand, ISI/fair-balance present, PI reference, indication qualifiers from the PI, single-arm/post hoc language, absolute and superlative claims, 2253 flag, endorsement disclosure. Each returns `rule_id`, pass/fail and an evidence span. |
| Known-bad cases as ground truth | `evals/opdp_cases.jsonl`: 279 real violations quoted from FDA OPDP untitled and warning letters. Deterministic recall is measured on these. |
| Pairwise, blind, randomized; separate "send as is" flag | `evals/pairwise.jsonl`: violating claim vs. a compliant rewrite, with A/B order randomized and a known winner. The judge answers one rule question ("which version better satisfies it?") and separately "approvable as is?" for each side (`judge/`). |
| Judge sanity checks on known winners | Easy pairs (original letter-cited claim vs. a rewrite that fixes the cited problem) come first. Near-miss pairs, where both sides look plausible and only one fixes the issue, test sensitivity. A judge that fails the easy pairs is not used on close calls. |
| Synthesis failure vs. missing context | Each pair carries `context_needed`, e.g., `pi_text` (needs the label to judge), `asset_visuals` (the letter describes visuals Margin cannot see), or `none`. A failure where context was required is logged as missing-context, not synthesis. |
| Agent draft vs. lawyer-final as the data engine | Not available yet. The equivalent is PromoMats draft → MLR-approved final with reviewer comments. Until then, controls are **synthetic** rewrites grounded in FDA's stated rationale and labeled as synthetic. |
| Workbench; experts own context, not prompts | Out of scope for this phase. Rules (`rules/`) and PI/claims-library inputs are kept separate from judge prompts so MLR reviewers could edit the rules without touching prompts. |

## Departures and limits

- Crosby's pairs are real agent-vs-lawyer outputs. Ours are FDA-cited claims vs. synthetic fixes, which are easier and less natural than production pairs. Treat pairwise accuracy here as a judge readiness floor (Crosby's "obvious cases"), not as a measure of review quality.
- No inter-rater agreement has been measured yet. Crosby's 45% agreement result implies MLR reviewers will also disagree, so a human-labeled subset is needed before any judge score is trusted.
