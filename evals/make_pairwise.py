"""Builds the pairwise eval set (blind A/B, seeded random order).
 - easy pairs: OPDP original (letter-quoted claim) vs its SYNTHETIC compliant rewrite (controls.jsonl)
 - near_miss pairs: hand-authored SYNTHETIC fictional pairs (near_miss_src.py + near_miss_src2.py)
Each item carries ONE rule question (+ anchors), expected_winner, and its split (dev/holdout from evals/splits.json).
build_items(opts) is used by the loop to build variants without writing files:
  opts.rule_assignment: 'first_judgment' (v1: first judgment rule linked to the case) | 'category_match' (rule chosen from the letter's category)
  opts.rule_overrides: {rule_id: {rule_text, question, pass_anchor, fail_anchor}}   (rule_text-layer changes; need human review)
Originals that are only the letter's description of an omission/process (no piece text) are excluded."""
import json, os, sys, random, re, collections
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0] = [f'{B}/evals', f'{B}/scripts']
from common import load_jsonl, load_rules, path
from near_miss_src import NEAR_MISS
try: from near_miss_src2 import NEAR_MISS_2
except ImportError: NEAR_MISS_2 = []
DESCRIPTIVE = r'^\s*(\[(Omission|Process|Format|Ordering)\]|The (TV|video|webpage|exhibit|major|ad)\b|A copy of|Major statement|Video prominently|\w+ TV Ad suggests|Beginnings of|Page four|.*\bfails? to\b.*$)'
CATEGORY_RULE = {  # letter category -> the rule whose question matches what FDA actually objected to
 'Overstatement of efficacy': 'A-202-E5-01', 'Unsupported PRO / quality-of-life claims': 'A-202-E5-01', 'Unsubstantiated efficacy / mechanism claims': 'A-202-E5-01',
 'Omission of risk information': 'A-202-E7-08', 'Lack of fair balance / risk prominence': 'A-202-E7-08',
 'Distracting presentation during risk/major statement (TV)': 'B-CCN-05', 'Major statement not in dual modality (TV)': 'B-CCN-03',
 'Misleading presentation of study data (post hoc / exploratory / single-arm)': 'B-CFL-03', 'Minimization of risk': 'A-202-E6-04J',
 'Misleading claims about safety': 'A-202-E6-04J', 'Broadening of indication / omission of material indication facts': 'A-202-E6-01J',
 'Unsubstantiated superiority / comparative claims': 'A-202-E6-02', 'Promotion of investigational / unapproved drug or use': 'A-202-E4-01',
 'Misleading administration / storage / handling presentation': 'B-CFL-01', 'Misleading representation of drug identity/source': 'A-202-E6-16',
 'Misleading citation of treatment guidelines / references': 'A-202-E6-09', 'Missing adequate provision / brief summary': 'A-202-E1-01',
 'Failure to use established name / required labeling elements': 'A-502N-01', 'Failure to submit at first use (Form FDA 2253)': 'A-314-81-01'}
def rule_fields(r, overrides=None):
    o = (overrides or {}).get(r['id'], {}); d = r['detection']
    if r['check_type'] == 'judgment': q, pa, fa = d['question'], d['pass_anchor'], d['fail_anchor']
    else:
        q = f"Does the piece satisfy this requirement: {o.get('rule_text', r['rule_text'])}"
        pa = 'Requirement met on the face of the text provided. Judge the text only; do not fail it for missing metadata, files or sign-offs the piece would not itself contain.'
        fa = 'The text itself shows the requirement is not met (e.g., the required element is absent, or the problematic claim/construct is present without the required qualification).'
    return dict(rule_id=r['id'], rule_source=f"{r['source']['document']}, {r['source']['section']}", rule_text=o.get('rule_text', r['rule_text']),
                rule_question=o.get('question', q), pass_anchor=o.get('pass_anchor', pa), fail_anchor=o.get('fail_anchor', fa),
                rule_check_type=r['check_type'], rule_family=r['id'][0])
def build_items(opts=None):
    opts = opts or {}; rules = load_rules(); cases = {c['id']: c for c in load_jsonl(path('cases'))}
    splits = json.load(open(path('splits'))) if os.path.exists(path('splits')) else {'case_split': {}, 'near_miss_split': {}}
    by_case = collections.defaultdict(list)
    for r in rules.values():
        for cid in r['opdp_case_ids']: by_case[cid].append(r)
    def pick_rule(cid):
        if opts.get('rule_assignment') == 'category_match':
            rid = CATEGORY_RULE.get(cases[cid]['category'])
            if rid in rules: return rules[rid]
        rs = by_case.get(cid, []); j = [r for r in rs if r['check_type'] == 'judgment']
        return (j or rs or [rules['A-502A-01']])[0]
    rng = random.Random(20261007); items = []
    for k in load_jsonl(path('controls')):
        if re.search(DESCRIPTIVE, k['original_claim'], re.I | re.S) and not k['original_claim'].lstrip().startswith(('“', '[Visual]', 'VO', 'SUPER')): continue
        case = cases[k['source_case_id']]; bad, good = k['original_claim'], k['compliant_rewrite']
        if opts.get('normalize_quotes'):  # remove typographic cues that reveal which side is the letter quote
            bad, good = (re.sub(r'[“”]', '"', x) for x in (bad, good))
        a_good = rng.random() < 0.5
        items.append(dict(id='PW-' + k['source_case_id'], kind='easy', synthetic_side='compliant rewrite (' + k['generator'] + ')', source_case_id=k['source_case_id'],
                          control_id=k['id'], category=case['category'], product=k['product'], piece_type=k['piece_type'], audience=k['audience'],
                          label_facts=case.get('context') or 'Not provided (judge from the text).', context_needed=k['context_needed'],
                          A=good if a_good else bad, B=bad if a_good else good, expected_winner='A' if a_good else 'B',
                          split=splits['case_split'].get(k['source_case_id'], 'dev'), **rule_fields(pick_rule(k['source_case_id']), opts.get('rule_overrides'))))
    for n in NEAR_MISS + (NEAR_MISS_2 if opts.get('include_nm2', True) else []):
        a_good = rng.random() < 0.5
        items.append(dict(id='PW-' + n['id'], kind='near_miss', synthetic_side='both (fictional product; agent-authored)', source_case_id=n['inspired_by'],
                          category=None, product=n['product'], piece_type=n['piece_type'], audience=n['audience'], label_facts=n['label'], context_needed='none',
                          A=n['good'] if a_good else n['bad'], B=n['bad'] if a_good else n['good'], expected_winner='A' if a_good else 'B', why=n['why'],
                          split=splits['near_miss_split'].get(n['id'], 'dev'), **rule_fields(rules[n['rule']], opts.get('rule_overrides'))))
    return [dict(synthetic=True, **it) for it in items]
def main():
    sys.path.insert(0, f'{B}/scripts')
    from engine import active_opts
    items = build_items(active_opts())
    with open(f'{B}/evals/pairwise.jsonl', 'w') as f:
        for it in items: f.write(json.dumps(it, ensure_ascii=False) + '\n')
    c = collections.Counter((i['kind'], i['split']) for i in items); w = collections.Counter(i['expected_winner'] for i in items)
    print('pairwise', len(items), dict(c), 'expected winner balance', dict(w))
if __name__ == '__main__': main()
