# dev split

Frozen by `evals/split.py` (seed 20261008); letter-grouped, stratified by year, audience, check type and rule family.

Used for triage and tuning.

Files: cases.jsonl (letter cases), controls.jsonl (compliant rewrites of those cases), pairs.jsonl (pairwise items incl. near-miss). Regenerate with `python3 evals/write_split_files.py`.
