"""Runs checks/ over (1) every deterministic OPDP case -> recall, (2) every control -> false positives.
Writes evals/det_results.json. Recall is computed per check over cases whose linked rules use that check and where the
check could run on letter-derived inputs (status pass/fail). Checks whose fixture merely restates the letter (metadata) are reported separately."""
import json, os, sys, collections
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, B); sys.path.insert(0, os.path.join(B, 'evals'))
from checks import run_checks, load_rules
from fixtures import case_fixture
TAUTOLOGICAL = {'form_2253'}  # fixture restates the letter's finding -> trivially 100%
CLAIM_LEVEL = {'efficacy_absolutes', 'control_group_data', 'qol_claim', 'comparative_claim', 'exclusivity_claim', 'minimization_lexicon', 'not_a_class',
               'posthoc_language', 'guideline_citation', 'fda_approval_misuse', 'single_arm_endpoints', 'relative_without_absolute', 'nonclinical_data',
               'pvalue_exploratory', 'testimonial_typicality', 'investigational_disclosure', 'indication_qualifiers'}
def group(fn):  # how to read a check's numbers on letter excerpts
    if fn in TAUTOLOGICAL: return 'tautological'
    return 'claim_level' if fn in CLAIM_LEVEL else 'whole_piece'
rules = {r['id']: r for r in load_rules()}
fn_of = {rid: r['detection'].get('check_fn') for rid, r in rules.items() if r['check_type'] == 'deterministic'}
expected = collections.defaultdict(set)
for rid, r in rules.items():
    if r['check_type'] == 'deterministic':
        for cid in r['opdp_case_ids']: expected[cid].add(rid)
cases = [json.loads(l) for l in open(f'{B}/evals/opdp_cases.jsonl')]
det = [c for c in cases if c['check_type'] == 'deterministic']
per = collections.defaultdict(lambda: dict(linked=0, evaluable=0, fired=0, needs_input=0, not_applicable=0, cases_fired=[], cases_missed=[]))
rows = []; case_caught = 0; case_eval = 0; any_fire = 0; no_link = []
for c in det:
    fx = case_fixture(c); res = run_checks(fx); by = {r['rule_id']: r for r in res}
    exp = expected.get(c['id'], set()); exp_fns = {fn_of[r] for r in exp}
    if not exp: no_link.append(c['id'])
    fired_fns = {r['check'] for r in res if r['status'] == 'fail'}
    for fn in exp_fns:
        stats = [by[r] for r in exp if fn_of[r] == fn]
        st = 'fail' if any(s['status'] == 'fail' for s in stats) else ('pass' if any(s['status'] == 'pass' for s in stats) else stats[0]['status'])
        p = per[fn]; p['linked'] += 1
        if st in ('pass', 'fail'):
            p['evaluable'] += 1
            if st == 'fail': p['fired'] += 1; p['cases_fired'].append(c['id'])
            else: p['cases_missed'].append(c['id'])
        else: p[st if st in ('needs_input', 'not_applicable') else 'needs_input'] += 1
    ev_fns = [fn for fn in exp_fns if fn not in TAUTOLOGICAL and any(by[r]['status'] in ('pass', 'fail') for r in exp if fn_of[r] == fn)]
    if ev_fns:
        case_eval += 1; case_caught += any(fn in fired_fns for fn in ev_fns)
    any_fire += bool(fired_fns - TAUTOLOGICAL)
    rows.append(dict(case_id=c['id'], category=c['category'], fixture_text=fx['text'][:300], expected_rules=sorted(exp),
                     fired=[dict(rule_id=r['rule_id'], check=r['check'], evidence=[e['text'] for e in r['evidence'][:2]]) for r in res if r['status'] == 'fail']))
# controls
ctrl_path = f'{B}/evals/controls.jsonl'; fp = collections.defaultdict(lambda: dict(evaluated=0, fired=0, examples=[])); ctrl_rows = []; targeted = {}
if os.path.exists(ctrl_path):
    for l in open(ctrl_path):
        k = json.loads(l); res = run_checks(k['piece']); fired = [r for r in res if r['status'] == 'fail']
        tgt = {fn_of[r] for r in expected.get(k['source_case_id'], set())}
        for r in res:
            if r['check'] in tgt and r['status'] in ('pass', 'fail'):
                g = targeted.setdefault(r['check'], dict(evaluated=set(), fired=set()))
                g['evaluated'].add(k['id'])
                if r['status'] == 'fail': g['fired'].add(k['id'])
            if r['status'] in ('pass', 'fail'):
                f = fp[r['check']]; f['evaluated'] += 1
                if r['status'] == 'fail':
                    f['fired'] += 1
                    if len(f['examples']) < 3: f['examples'].append(dict(control=k['id'], rule=r['rule_id'], evidence=[e['text'] for e in r['evidence'][:1]], detail=r['detail'][:120]))
        ctrl_rows.append(dict(control_id=k['id'], n_fail=len({r['check'] for r in fired}), failed_checks=sorted({r['check'] for r in fired})))
out = dict(n_det_cases=len(det), cases_with_linked_rule=len(det) - len(no_link), cases_without_linked_rule=no_link,
           case_level=dict(evaluable=case_eval, caught=case_caught), any_check_fired=any_fire,
           per_check={k: dict(v, group=group(k)) for k, v in sorted(per.items())}, tautological=sorted(TAUTOLOGICAL),
           controls=dict(groups={k: group(k) for k in fp}, targeted={k: dict(evaluated=len(v['evaluated']), fired=len(v['fired']), controls_fired=sorted(v['fired']), controls_evaluated=sorted(v['evaluated'])) for k, v in sorted(targeted.items())},
                         n=len(ctrl_rows), with_any_claim_level_fail=sum(1 for r in ctrl_rows if set(r['failed_checks']) & CLAIM_LEVEL), with_any_fail=sum(1 for r in ctrl_rows if r['n_fail']), per_check={k: v for k, v in sorted(fp.items())}, rows=ctrl_rows), case_rows=rows)
json.dump(out, open(f'{B}/evals/det_results.json', 'w'), indent=1, ensure_ascii=False)
print('det cases', len(det), '| linked', len(det) - len(no_link), '| case-level recall', f'{case_caught}/{case_eval}', '| any non-tautological check fired', any_fire)
for k, v in sorted(per.items(), key=lambda x: -x[1]['linked']):
    print(f"{k:28} linked {v['linked']:3} eval {v['evaluable']:3} fired {v['fired']:3} needs_input {v['needs_input']:3} n/a {v['not_applicable']:3}")
if ctrl_rows:
    print('controls', len(ctrl_rows), 'with any fail', out['controls']['with_any_fail'])
    for k, v in sorted(fp.items(), key=lambda x: -x[1]['fired']):
        if v['fired']: print(f"  FP {k:28} {v['fired']}/{v['evaluated']}")
