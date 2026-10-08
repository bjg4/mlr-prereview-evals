# Kickstart: from zero to a working pre-review loop

This takes about a week of part-time work. Every step writes files you can read. Nothing is sent anywhere.

## 0. What to provide

| Need | Why | Where it goes |
|---|---|---|
| **LLM API key** (e.g., OpenRouter) and a budget | Judge, triage, rewrite drafting | Key in a private file (e.g., `~/.config/openrouter/api_key`, chmod 600). Point `config.yaml → judge.api_key_file` at it. Set `budget.phase_cap_usd`. |
| **Product labels** (PI, medication guide) | Authoritative label facts | PDFs or text in `pieces/pi/`; short excerpts in `pieces/pi_facts.json` |
| **Pieces to review** | What gets pre-reviewed | One folder per piece in `pieces/<slug>/` with `page.txt` and `meta.json` (brand, established_name, audience) |
| **Claims library, SOPs, past MLR decisions** (strongly recommended) | Company-specific rules and real labeled positives and negatives | Add as rules (`rules/`) and eval cases; past "approved" and "rejected with comments" decisions are the best eval data you will ever have |
| **A named human reviewer** | Labels, rule-text sign-off | Name them in proposals (`approved_by`) and eval-data logs (`--reviewer`) |
| Optional: literature-search API (e.g., PubMed or Exa) | Reference and claim-support checks | Not wired by default; add as a check that writes evidence to `meta.reference_checks` |

## 1. Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # system: poppler-utils (pdftotext)
```

## 2. Build the letter set, rules, checks and evals (no API cost if caches exist)

```bash
python3 scripts/build.py                   # letters -> cases, rules, controls, deterministic checks, frozen split, pairs, report
```

- **New letters:** add rows to `scripts/index_rows.tsv` (untitled) or `scripts/wl_rows.tsv` (warning), add their text to `letters/text/`, write the per-letter case JSON in `scripts/cases/`, then rebuild.
- **New rules:** edit `scripts/rules_src.py` (quote the source; set `check_type` and `detection`), then run `python3 scripts/build_rules.py`.
- **The split:** `evals/split.py` freezes it once. Do not rebuild it (`--force`) without logging a ledger row.

## 3. Calibrate the judge

```bash
python3 judge/run_judge.py --paid          # pairwise + single-item on the eval set; writes judge/results/status.json
```

Pairwise accuracy on easy pairs should be near 100%. If it isn't, fix the prompt or model before going further. The honest numbers are single-item specificity and sensitivity.

## 4. Run the loop

```bash
python3 scripts/loop.py --round 1          # score -> triage -> loop/proposals/round_1.json -> evaluate approved proposals
# read evals/triage/round_1.jsonl and loop/proposals/round_1.json; set "approved": true + "approved_by" on the ones you accept
python3 scripts/loop.py --round 1 --evaluate-only
python3 scripts/loop.py --round 2 --auto-approve   # auto-approves only judge-prompt / rule-assignment proposals
```

Fixed an eval item? Log it as a re-baseline. It is never scored as an improvement:

```bash
python3 scripts/loop.py --round 2 --eval-data E5-fix-xyz --desc "what changed and why" --files evals/controls_manual.py --reviewer "Reviewer Name"
```

Outputs:
- `evals/scoreboard/round_N.md` (metrics)
- `evals/ledger.jsonl` (every change: accepted or rejected, with dev and holdout deltas)
- `loop/state.json` (what is live)
- `loop/spend.json` (cost)

## 5. Pre-review real pieces

```bash
python3 scripts/field_prereview.py         # writes pieces/prereview_<slug>.md (flags with rule ids + evidence spans)
```

Have the reviewer label each flag as true issue, false alarm, or needs visuals. Each label becomes a new eval case, and this is how the eval set becomes yours.

## First-week plan

| Day | Do |
|---|---|
| 1 | Connect the key, set the budget, run `build.py`, read `evals/report.md` and `docs/HOW-IT-WORKS.md`. Add your product PIs and 3–5 real pieces. |
| 2 | Run the judge calibration. Have the reviewer skim 20 controls and 10 near-miss pairs and fix or flag bad ones (log as eval-data changes). |
| 3 | Import 20–50 past MLR decisions (claim + outcome + reviewer comment) as cases. Add company SOP or claims-library rules with source quotes. |
| 4 | Run `loop.py --round 1`. The reviewer approves or rejects proposals. Read the ledger together. |
| 5 | Run `field_prereview.py` on real pieces. The reviewer labels the flags. Add them as cases. Run round 2. Decide what metric threshold makes the tool useful (for example, specificity ≥ 0.85 at sensitivity ≥ 0.9 on holdout). |
