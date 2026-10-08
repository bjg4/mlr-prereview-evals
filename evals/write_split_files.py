"""Materialize the frozen split (evals/splits.json) into evals/holdout/ and evals/dev/ so the holdout is physically separate.
Tuning tools (triage, proposal drafting) only ever read DEV rows; holdout files are for scoring only. Rebuild: python3 evals/write_split_files.py"""
import os, sys, json
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0] = [f'{B}/scripts', f'{B}/evals']
from common import load_jsonl, write_jsonl, path
from make_pairwise import build_items
import engine
S = json.load(open(path('splits'))); cs, ns = S['case_split'], S['near_miss_split']
cases = load_jsonl(path('cases')); ctrls = load_jsonl(path('controls')); items = build_items(engine.active_opts())
for sp in ('dev', 'holdout'):
    d = f'{B}/evals/{sp}'; os.makedirs(d, exist_ok=True)
    write_jsonl(f'{d}/cases.jsonl', [c for c in cases if cs.get(c['id']) == sp])
    write_jsonl(f'{d}/controls.jsonl', [k for k in ctrls if cs.get(k['source_case_id']) == sp])
    write_jsonl(f'{d}/pairs.jsonl', [i for i in items if i['split'] == sp])
    open(f'{d}/README.md', 'w').write(f"# {sp} split\n\nFrozen by `evals/split.py` (seed {S['seed']}); letter-grouped, stratified by year, audience, check type and rule family.\n"
        + ("\n**Holdout: never used for triage, proposals or prompt writing. Score only, through the acceptance rule.**\n" if sp == 'holdout' else '\nUsed for triage and tuning.\n')
        + f"\nFiles: cases.jsonl (letter cases), controls.jsonl (compliant rewrites of those cases), pairs.jsonl (pairwise items incl. near-miss). Regenerate with `python3 evals/write_split_files.py`.\n")
    print(sp, 'cases', sum(cs.get(c['id']) == sp for c in cases), 'controls', sum(cs.get(k['source_case_id']) == sp for k in ctrls), 'pairs', sum(i['split'] == sp for i in items))
