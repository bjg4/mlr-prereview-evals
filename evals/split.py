"""Freeze a dev/holdout split. Run once; re-running with the same seed reproduces it exactly.
Unit of splitting = the source LETTER (all cases, controls and pairs from one letter go to the same side, so no piece leaks
across splits). Letters are stratified by (letter-year bucket, audience, majority check_type, dominant rule family) and within each
stratum a seeded shuffle sends ~holdout_fraction to holdout. Synthetic near-miss pairs are split separately, stratified by rule family.
The 6 captured homepages in pieces/ are the unlabeled FIELD set (never scored).
Holdout is used ONLY by the loop's acceptance check; triage and proposal generation read dev only."""
import os, sys, json, random, collections, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from common import CFG, path, load_jsonl, load_rules, rel
def year_bucket(y): return '2020-2023' if y <= '2023' else ('2024-2025' if y <= '2025' else '2026')
def main(force=False):
    out = path('splits')
    if os.path.exists(out) and not force:
        print('split already frozen:', out, '(use --force to rebuild; this changes the holdout and must be logged)'); return json.load(open(out))
    seed, frac = CFG['split']['seed'], CFG['split']['holdout_fraction']
    cases = load_jsonl(path('cases')); rules = load_rules()
    fam_of = collections.defaultdict(collections.Counter)
    for r in rules.values():
        for cid in r['opdp_case_ids']: fam_of[cid][r['id'][0]] += 1
    letters = collections.defaultdict(list)
    for c in cases: letters[c['source_letter']].append(c)
    def stratum(lid):
        cs = letters[lid]; fam = collections.Counter()
        for c in cs: fam.update(fam_of[c['id']])
        ct = collections.Counter(c['check_type'] for c in cs).most_common(1)[0][0]
        return (year_bucket(cs[0]['letter_date'][:4]), cs[0]['audience'], ct, fam.most_common(1)[0][0] if fam else '-')
    strata = collections.defaultdict(list)
    for lid in sorted(letters): strata[stratum(lid)].append(lid)
    rng = random.Random(seed); hold = set(); carry = 0.0
    for key in sorted(strata):
        ls = strata[key][:]; rng.shuffle(ls)
        want = len(ls) * frac + carry; k = int(want); carry = want - k  # carry fractional remainder across strata
        hold.update(ls[:k])
    nm = {}
    sys.path.insert(0, rel('evals'))
    from near_miss_src import NEAR_MISS
    try:
        from near_miss_src2 import NEAR_MISS_2
    except ImportError: NEAR_MISS_2 = []
    byfam = collections.defaultdict(list)
    for n in NEAR_MISS + NEAR_MISS_2: byfam[n['rule'][0]].append(n['id'])
    rng2 = random.Random(seed + 1); carry = 0.0
    for f in sorted(byfam):
        ids = sorted(byfam[f]); rng2.shuffle(ids); want = len(ids) * frac + carry; k = int(want); carry = want - k
        for i in ids: nm[i] = 'holdout' if i in ids[:k] else 'dev'
    case_split = {c['id']: ('holdout' if c['source_letter'] in hold else 'dev') for c in cases}
    pieces = sorted(d for d in os.listdir(path('pieces_dir')) if os.path.isdir(os.path.join(path('pieces_dir'), d)) and d != 'pi')
    S = dict(seed=seed, holdout_fraction=frac, unit='source_letter', strata_keys=['letter_year_bucket', 'audience', 'majority_check_type', 'dominant_rule_family'],
             holdout_letters=sorted(hold), dev_letters=sorted(set(letters) - hold), case_split=case_split, near_miss_split=nm, field_set=pieces,
             note='Frozen 2026-10-08 after phases 1-2. The build agent had already seen every letter case while writing checks/rewrites, so holdout protects against overfitting from this point on, not retroactively.')
    json.dump(S, open(out, 'w'), indent=1)
    # balance report
    def dist(ids, key): return dict(collections.Counter(key(c) for c in cases if c['id'] in ids))
    for side in ('dev', 'holdout'):
        ids = {k for k, v in case_split.items() if v == side}
        print(side, 'letters', sum(1 for l in letters if (l in hold) == (side == 'holdout')), 'cases', len(ids),
              'check_type', dist(ids, lambda c: c['check_type']), 'audience', dist(ids, lambda c: c['audience']), 'year', dist(ids, lambda c: year_bucket(c['letter_date'][:4])),
              'family', dict(sum((fam_of[i] for i in ids), collections.Counter())))
    print('near-miss', collections.Counter(nm.values()), 'field', pieces)
    return S
if __name__ == '__main__': main(force='--force' in sys.argv)
