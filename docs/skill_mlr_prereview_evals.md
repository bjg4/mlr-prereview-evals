---
name: mlr-prereview-evals
description: Build, run and improve an MLR (medical-legal-regulatory) pre-review of pharma promotional pieces with Crosby-style evals, plus a ledgered self-improvement loop. Use when someone asks to pre-review a promotional piece, build or extend the rulebook or evals, calibrate the judge, or run a loop round.
---

# MLR pre-review with Crosby-style evals

**Guardrails (always):**
- You produce *pre-review flags*, never approvals.
- Never send, post or submit anything.
- Every flag cites a rule ID and quotes an exact span from the piece.
- Label synthetic content `synthetic: true`.
- Read API keys from the configured file at runtime only; never print or write them.
- Stay inside `config.yaml → budget.phase_cap_usd` and report spend from `loop/spend.json`.

## Workflow

1. **Inputs.** Each piece is a folder in `pieces/<slug>/` with `page.txt` and `meta.json` (brand, established_name, audience). Label facts live in `pieces/pi_facts.json`, excerpted from the PI. If the PI is missing, ask for it. Do not guess label facts.
2. **Rules.** Rules live in `rules/*.json`, one per requirement, with a source quote, `check_type` (deterministic or judgment) and `detection`. New rules go in `scripts/rules_src.py`, then run `python3 scripts/build_rules.py`. Never write a rule without a source section.
3. **Evals.** Run `python3 scripts/build.py` to rebuild:
   - cases from FDA letters (positives)
   - controls (compliant rewrites; negatives)
   - pairwise and near-miss sets
   - the frozen dev/holdout split (`evals/splits.json`)
   - the report

   The holdout is for scoring only. Never read holdout failures when writing prompts or rules.
4. **Deterministic first.** `checks/margin_checks.py` runs before the LLM. Track recall on cases and the false-positive rate on controls.
5. **Judge.** Pairwise (both A/B orders) and single-item pass/fail, both with evidence. Report single-item sensitivity and specificity as the honest numbers. Pairwise accuracy saturates.
6. **Loop round.** Run `python3 scripts/loop.py --round N`:
   - score
   - triage dev failures into one layer each (`rule_text`, `rule_assignment`, `eval_data`, `det_check`, `judge_prompt`, `judge_model`, `input_gap`) → `evals/triage/round_N.jsonl`
   - write proposals → `loop/proposals/round_N.json`
   - evaluate approved proposals

   Only judge-prompt and rule-assignment proposals may be auto-approved (`--auto-approve`). Rule text and eval labels need a named human.
7. **Acceptance rule.** Accept a change only if all of these hold:
   - its target metric improves on dev
   - dev balanced accuracy does not drop beyond noise
   - holdout balanced accuracy and holdout pairwise accuracy do not drop beyond noise
   - no dev rule-family slice (n ≥ 4 each side) drops beyond noise
   - neither dev sensitivity nor dev specificity drops by more than 2× noise

   Noise = max(1/n, √(p(1−p)/n)). Every decision goes to `evals/ledger.jsonl`.
8. **Eval-data edits** (fixing a rewrite, adding pairs) are logged with `--eval-data ID --reviewer NAME` and re-baselined. Never count them as improvements.
9. **Field pre-review.** Run `python3 scripts/field_prereview.py [slug]` to write `pieces/prereview_<slug>.md` with verified evidence spans. Ask the human to label each flag (true issue / false alarm / needs visuals) and turn those labels into eval cases.
10. **Report.** Give:
    - split sizes
    - ledger summary (accepted and rejected, with dev and holdout deltas)
    - before/after scoreboard (sensitivity, specificity, balanced accuracy, pairwise, position bias, det recall and FP rate)
    - spend
    - top flags per piece
    - remaining gaps

## Pitfalls

- Placeholder text, curly quotes or length differences leak which side is compliant. Remove them before trusting pairwise results.
- Judge rule assignment must match the letter's cited category.
- Text-only review cannot judge visual prominence or audio. Mark these `input_gap` instead of guessing.
- Small slices are noisy. Do not chase single-item swings.
