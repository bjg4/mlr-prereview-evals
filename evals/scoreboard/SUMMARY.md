# Loop summary: before vs after

Phase spend: $2.02 of $3.00 cap. Judge `anthropic/claude-haiku-5.5`.

- **Before** = round 0: pre-loop pipeline on the original eval data (placeholder rewrites, no NM-28..51).
- **Re-baselined** = same pipeline after the eval-data fixes (harder, cleaner test): the fair starting point for loop gains.
- **After** = accepted state after round 2.

## dev

| Metric | Before (r0) | Re-baselined | After |
|---|---|---|---|
| Judge sensitivity (violating → fail) | 0.924 | 0.939 | 0.966 |
| Judge specificity (compliant → pass) | 0.603 | 0.708 | 0.728 |
| Judge balanced accuracy | 0.763 | 0.823 | 0.847 |
| Near-miss balanced accuracy | 0.881 | 0.932 | 0.946 |
| Easy balanced accuracy | 0.741 | 0.786 | 0.814 |
| Pairwise accuracy | 0.996 | 1.000 | 1.000 |
| Position: acc when correct=A | 1.000 | 1.000 | 1.000 |
| Position: acc when correct=B | 0.992 | 1.000 | 1.000 |
| Order flips (pairs) | 1 | 0 | 0 |
| Det claim-level recall | 0.823 | 0.823 | 0.823 |
| Det targeted FP rate on controls | 0.083 | 0.196 | 0.196 |

Items: before {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 21, 'near_miss/holdout': 6}; after {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 37, 'near_miss/holdout': 14}. Single-item n (pos/neg) after: 147/147.

## holdout

| Metric | Before (r0) | Re-baselined | After |
|---|---|---|---|
| Judge sensitivity (violating → fail) | 0.922 | 0.932 | 0.966 |
| Judge specificity (compliant → pass) | 0.647 | 0.750 | 0.700 |
| Judge balanced accuracy | 0.784 | 0.841 | 0.833 |
| Near-miss balanced accuracy | 1.000 | 0.964 | 0.964 |
| Easy balanced accuracy | 0.755 | 0.803 | 0.793 |
| Pairwise accuracy | 1.000 | 0.992 | 0.983 |
| Position: acc when correct=A | 1.000 | 1.000 | 0.983 |
| Position: acc when correct=B | 1.000 | 0.983 | 0.983 |
| Order flips (pairs) | 0 | 1 | 2 |
| Det claim-level recall | 0.923 | 0.923 | 0.923 |
| Det targeted FP rate on controls | 0.191 | 0.238 | 0.238 |

Items: before {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 21, 'near_miss/holdout': 6}; after {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 37, 'near_miss/holdout': 14}. Single-item n (pos/neg) after: 59/60.

Coverage (rules with ≥1 positive and ≥1 negative): before 56/81, after 78/81.

## Ledger

| Round | Change | Kind / layer | Decision | dev BA Δ | dev sens Δ | dev spec Δ | holdout BA Δ | holdout pairwise Δ | Reason |
|---|---|---|---|---|---|---|---|---|---|
| 1 | E1-photofrin-rewrite | eval_data / eval_data | re-baselined (eval-data change; not judg | 0.004 | 0.000 | 0.008 | 0.000 | 0.000 | Hand-fix the Photofrin compliant rewrite (CTRL-UL-20260622-193307-v3): v1 rewrite kept an implied-safety statement; new text states the >1 c |
| 1 | E2-deplaceholder | eval_data / eval_data | re-baselined (eval-data change; not judg | 0.046 | 0.000 | 0.092 | 0.051 | -0.019 | Remove placeholder leakage: 152/160 bracketed compliant rewrites re-written without placeholders (no new numbers allowed; 8 rejected, v1 kep |
| 1 | E3-near-miss-2 | eval_data / eval_data | re-baselined (eval-data change; not judg | 0.020 | 0.008 | 0.032 | 0.014 | 0.003 | Add 24 agent-authored near-miss pairs (NM-28..NM-51, fictional products) targeting the 23 rules with no positive+negative coverage plus the  |
| 1 | E4-normalize-quotes | eval_data / eval_data | re-baselined (eval-data change; not judg | -0.010 | 0.007 | -0.027 | -0.008 | 0.008 | Normalize curly quotes to straight quotes on both sides of every easy pair, so typography no longer reveals which side is the verbatim lette |
| 1 | C1-reminder-boxed-warning | variant / rule_text | accepted_pending_human_review | 0.003 | 0.007 | 0.000 | 0.000 | 0.000 | dev judge_balanced_accuracy +0.0034; no holdout/slice regression beyond noise |
| 1 | C2-pair-category-match | variant / rule_assignment | rejected | 0.020 | 0.020 | 0.020 | -0.008 | -0.008 | holdout pairwise_accuracy regressed -0.0084 (noise 0.0083) |
| 1 | C3-tighten-soft-claims | variant / judge_prompt | rejected | -0.051 | 0.020 | -0.122 | -0.050 | -0.017 | dev judge_balanced_accuracy regressed -0.0511 (noise 0.0312); holdout judge_balanced_accuracy regressed -0.0496 (noise 0.0476); holdout pair |
| 1 | C4-loosen-trigger-only | variant / judge_prompt | rejected | 0.017 | -0.095 | 0.129 | -0.018 | -0.008 | holdout pairwise_accuracy regressed -0.0084 (noise 0.0083) |
| 2 | X1-acceptance-rule-fix | process / loop | applied (process change; acceptance-rule | — | — | — | — | — | Rounding fix restores the stated rule; guard (5) uses dev only so holdout stays untouched for design. Note: C4 holdout deltas were already v |
| 2 | C2r-pair-category-match-recheck | variant / rule_assignment | accepted | 0.020 | 0.020 | 0.020 | -0.008 | -0.008 | dev judge_balanced_accuracy +0.0203; no holdout/slice/sens-spec regression beyond noise |
| 2 | C4r-loosen-trigger-only-recheck | variant / judge_prompt | rejected | 0.003 | -0.102 | 0.109 | -0.009 | 0.000 | dev single_sensitivity dropped -0.1021 (> 2x noise 0.0299) |
| 2 | P2-judge-too_strict | variant / judge_prompt | rejected | 0.017 | -0.143 | 0.177 | 0.024 | -0.008 | dev single_sensitivity dropped -0.1429 (> 2x noise 0.0299) |
| 2 | P2-judge-too_lenient | variant / judge_prompt | rejected | -0.109 | 0.020 | -0.238 | -0.100 | -0.008 | dev judge_balanced_accuracy regressed -0.1088 (noise 0.0297); holdout judge_balanced_accuracy regressed -0.0997 (noise 0.0486); dev family A |

Eval-data rows compare different tests, so their Δ is a re-baseline, not an improvement.
