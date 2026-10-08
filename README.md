# mlr-prereview-evals

An open toolkit for AI **pre-review of pharmaceutical promotional material** (the MLR step: medical, legal, regulatory).
It flags likely problems in a piece, with evidence quotes and rule citations, so a human MLR reviewer can work faster. It never approves anything and never sends anything.
It ships with an eval set built from FDA OPDP untitled and warning letters, a cited rulebook, deterministic checks, an LLM judge, and a ledgered self-improvement loop.
The evaluation design follows Crosby's method ("How we do evals at Crosby", https://crosby.ai/blog/how-we-do-evals-at-crosby): deterministic checks first, then blind randomized pairwise review with a separate pass/fail flag, then judge calibration on known winners. Missing-context failures are kept separate from reasoning failures.

- **How it works:** [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md)
- **Start from zero:** [docs/KICKSTART.md](docs/KICKSTART.md)
- **Bot skills:** [docs/skill_mlr_prereview_evals.md](docs/skill_mlr_prereview_evals.md), [docs/skill_getting_started.md](docs/skill_getting_started.md)
- **Method notes:** [method.md](method.md). **Latest results:** [evals/report.md](evals/report.md), [evals/scoreboard/SUMMARY.md](evals/scoreboard/SUMMARY.md)

## Quickstart

```bash
git clone https://github.com/bjg4/mlr-prereview-evals && cd mlr-prereview-evals
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt                  # system dependency: poppler-utils (pdftotext) for new PDFs
python3 scripts/build.py                         # rules, controls, deterministic checks, frozen split, pairs, report: no API calls

# LLM steps (cost money; capped by config.yaml budget.phase_cap_usd). Put an OpenRouter key in a private file:
mkdir -p ~/.config/openrouter && chmod 700 ~/.config/openrouter
$EDITOR ~/.config/openrouter/api_key && chmod 600 ~/.config/openrouter/api_key   # or export OPENROUTER_API_KEY / OPENROUTER_API_KEY_FILE
python3 judge/run_judge.py --paid                # calibrate the judge on the eval set
python3 scripts/loop.py --round 3                # score -> triage -> proposals -> evaluate approved -> ledger + scoreboard
```

The included judge cache (`judge/results/cache.jsonl`) makes reruns of the shipped eval state free.

## Layout

| Layer | Where |
|---|---|
| FDA OPDP letters (manifest, PDFs, extracted text) | `letters/` |
| Rulebook (statute and regulations, FDA guidance, FTC, OIG, PhRMA), with archived source text | `rules/`, `rules/sources/` |
| Deterministic checks | `checks/margin_checks.py` |
| LLM judge, prompts and results | `judge/` |
| Eval sets: letter cases, compliant controls, pairwise, near-miss, frozen dev/holdout split, ledger, scoreboard | `evals/` |
| Self-improvement loop | `scripts/loop.py`, `scripts/engine.py`, `loop/` |
| Configuration (model, budget, paths; no secrets) | `config.yaml` |

## Field set (real pieces): generated locally, not included

Captured web pages, screenshots and manufacturer labeling (PI and Medication Guides) are third-party copyrighted, so they are not in this repo.
`pieces/manifest.json` lists the six public product homepages used during development (URLs and capture dates only).

To re-capture a piece:
1. Run `pip install playwright && playwright install chrome`, then `python3 scripts/capture_pieces.py` and `python3 scripts/finalize_pieces.py`. Edit the URL list in the script.
2. Put the product labeling text in `pieces/pi/`.
3. Copy `pieces/pi_facts.example.json` to `pieces/pi_facts.json` and fill it.
4. Run `python3 scripts/field_prereview.py`.

Pre-review reports (`pieces/prereview_<slug>.md`) are generated on your machine and are meant for your own reviewers.

## DATA NOTICE

- **FDA letters and government sources:** the OPDP untitled and warning letters in `letters/` and the archived statute, regulation and FDA/FTC/OIG text in `rules/sources/` are US government works in the public domain. Industry codes (PhRMA) are quoted briefly for citation.
- **Synthetic content:** compliant rewrites (`evals/controls*.jsonl`) and near-miss pairs (`evals/near_miss_src*.py`, fictional products) are **synthetic**. They are labeled `synthetic: true` with their generator, and have not been reviewed by a regulatory professional.
- **Not advice:** nothing here is legal or regulatory advice.
- **Flags, not approvals:** outputs are **pre-review flags for human MLR review, never approvals**. A clean run means "no flags found", not "compliant".
- **No secrets:** API keys are read from a file or environment variable at runtime and are never stored here.

## License

Code and docs: MIT (see [LICENSE](LICENSE)). Data: see the DATA NOTICE above.
