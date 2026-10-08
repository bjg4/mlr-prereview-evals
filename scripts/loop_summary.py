"""Write evals/scoreboard/SUMMARY.md: before (round 0, pre-loop) vs after (latest round) on the honest metrics, plus the ledger by round.
Note: round 0 and later rounds are scored on different eval data (eval-data changes re-baseline); the 're-baselined' column isolates loop gains."""
import os, sys, json, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import rel, CFG, load_jsonl
import engine as E
D = rel(CFG['paths']['scoreboard_dir'])
def ld(n): p = f'{D}/{n}.json'; return json.load(open(p)) if os.path.exists(p) else None
rounds = sorted(int(m.group(1)) for f in glob.glob(f'{D}/round_*.json') if (m := re.match(r'.*round_(\d+)\.json$', f)))
r0, rb, rl = ld('round_0'), ld('round_1_baseline'), ld(f'round_{rounds[-1]}')
def g(sb, sp, *ks):
    x = sb[sp]
    for k in ks: x = x.get(k) if isinstance(x, dict) else None
    return x
ROWS = [('Judge sensitivity (violating → fail)', ('judge', 'single', 'sensitivity')), ('Judge specificity (compliant → pass)', ('judge', 'single', 'specificity')),
        ('Judge balanced accuracy', ('judge', 'single', 'balanced_accuracy')), ('Near-miss balanced accuracy', ('judge', 'single_near_miss', 'balanced_accuracy')),
        ('Easy balanced accuracy', ('judge', 'single_easy', 'balanced_accuracy')), ('Pairwise accuracy', ('judge', 'pairwise', 'accuracy')),
        ('Position: acc when correct=A', ('judge', 'pairwise', 'acc_when_A')), ('Position: acc when correct=B', ('judge', 'pairwise', 'acc_when_B')),
        ('Order flips (pairs)', ('judge', 'pairwise', 'order_flips')), ('Det claim-level recall', ('det', 'claim_level_recall')), ('Det targeted FP rate on controls', ('det', 'targeted_fp_rate'))]
f = lambda v: '—' if v is None else (f'{v:.3f}' if isinstance(v, float) else str(v))
L = ['# Loop summary: before vs after', '', f'Phase spend: ${E.spend()["total_usd"]:.2f} of ${CFG["budget"]["phase_cap_usd"]:.2f} cap. Judge `{rl["judge_model"]}`.', '',
     '- **Before** = round 0: pre-loop pipeline on the original eval data (placeholder rewrites, no NM-28..51).',
     '- **Re-baselined** = same pipeline after the eval-data fixes (harder, cleaner test): the fair starting point for loop gains.',
     f'- **After** = accepted state after round {rounds[-1]}.', '']
for sp in ('dev', 'holdout'):
    L += [f'## {sp}', '', '| Metric | Before (r0) | Re-baselined | After |', '|---|---|---|---|']
    for name, ks in ROWS: L.append(f'| {name} | {f(g(r0, sp, *ks))} | {f(g(rb, sp, *ks))} | {f(g(rl, sp, *ks))} |')
    L.append(f"\nItems: before {r0['items']}; after {rl['items']}. Single-item n (pos/neg) after: {g(rl, sp, 'judge', 'single', 'n_pos')}/{g(rl, sp, 'judge', 'single', 'n_neg')}.\n")
L += [f"Coverage (rules with ≥1 positive and ≥1 negative): before {r0['coverage']['with_pos_and_neg']}/{r0['coverage']['rules']}, after {rl['coverage']['with_pos_and_neg']}/{rl['coverage']['rules']}.", '', '## Ledger', '',
      '| Round | Change | Kind / layer | Decision | dev BA Δ | dev sens Δ | dev spec Δ | holdout BA Δ | holdout pairwise Δ | Reason |', '|---|---|---|---|---|---|---|---|---|---|']
for r in load_jsonl(rel(CFG['paths']['ledger'])):
    m = r.get('metrics') or {}; d = lambda k: f(m.get(k, {}).get('delta')) if m.get(k) else '—'
    L.append(f"| {r['round']} | {r['change_id']} | {r['kind']} / {r.get('layer')} | {r['decision'][:40]} | {d('dev.judge_balanced_accuracy')} | {d('dev.single_sensitivity')} | {d('dev.single_specificity')} | {d('holdout.judge_balanced_accuracy')} | {d('holdout.pairwise_accuracy')} | {(r.get('reason') or r.get('hypothesis') or '')[:140]} |")
L += ['', 'Eval-data rows compare different tests, so their Δ is a re-baseline, not an improvement.', '']
open(f'{D}/SUMMARY.md', 'w').write('\n'.join(L)); print('wrote', f'{D}/SUMMARY.md')
