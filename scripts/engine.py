"""Margin self-improvement engine: variants, judging, scoring, acceptance. Used by scripts/loop.py.
A VARIANT = the accepted state (loop/state.json) plus zero or more candidate changes. Change types the engine can apply:
  judge_addendum      {"text": ...}                         -> appended to the judge SYSTEM prompt   (layer judge_prompt)
  pair_rule_assignment{"mode": "category_match"}            -> which rule each easy pair is judged on (layer rule_assignment)
  rule_override       {"rule_id", "rule_text"/"question"/...}-> rule wording the judge sees        (layer rule_text; needs human review)
  judge_model         {"model": ...}                         -> swap the judge model                   (layer judge_model; needs budget OK)
Eval-data edits (rewrites, labels, new items) are NOT variants: they are applied to files, logged as eval_data rows, and re-baselined."""
import os, sys, json, math, collections, datetime, subprocess
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__))]
from common import ROOT, CFG, path, rel, load_jsonl, write_jsonl, load_rules
sys.path[:0] = [rel('judge'), rel('evals')]
STATE = rel(CFG['paths']['loop_dir'], 'state.json')
SPEND = rel(CFG['paths']['loop_dir'], 'spend.json')
def now(): return datetime.datetime.now().astimezone().isoformat(timespec='seconds')
def load_state():
    if os.path.exists(STATE): return json.load(open(STATE))
    return dict(accepted=[], model=CFG['judge']['model'], created=now())
def save_state(st): os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(st, open(STATE, 'w'), indent=1)
def active_opts(extra=None):
    """Turn accepted changes (+ optional candidate changes) into builder/judge options."""
    st = load_state(); ch = st['accepted'] + (extra or [])
    o = dict(rule_assignment='first_judgment', rule_overrides={}, addenda=[], model=st.get('model') or CFG['judge']['model'], normalize_quotes=st.get('normalize_quotes', False))
    for c in ch:
        t, p = c['type'], c['payload']
        if t == 'judge_addendum': o['addenda'].append(p['text'])
        elif t == 'pair_rule_assignment': o['rule_assignment'] = p['mode']
        elif t == 'rule_override': o['rule_overrides'][p['rule_id']] = {k: v for k, v in p.items() if k != 'rule_id'}
        elif t == 'judge_model': o['model'] = p['model']
    return o
# ---------------------------------------------------------------- spend
def spend():
    return json.load(open(SPEND)) if os.path.exists(SPEND) else dict(phase='phase3', total_usd=0.0, events=[])
def add_spend(usd, what):
    s = spend(); s['total_usd'] = round(s['total_usd'] + usd, 5); s['events'].append(dict(at=now(), usd=round(usd, 5), what=what))
    os.makedirs(os.path.dirname(SPEND), exist_ok=True); json.dump(s, open(SPEND, 'w'), indent=1); return s['total_usd']
# ---------------------------------------------------------------- judge
def judge_items(items, opts, phases=('pairwise', 'single'), label='variant'):
    import llm, run_judge as rj
    llm.load_openrouter_key()
    if not llm.available(CFG['judge']['backend']): raise SystemExit('No judge API key available (see config.yaml judge.api_key_file)')
    ps, pu = rj.template('pairwise_prompt.md'); ss, su = rj.template('single_prompt.md')
    if opts.get('addenda'):
        add = '\n\nAdditional reviewer guidance (from the improvement loop):\n' + '\n'.join(f'- {a}' for a in opts['addenda'])
        ps, ss = ps + add, ss + add
    jobs = []
    for it in items:
        if 'pairwise' in phases:
            for order in ('orig', 'swapped'):
                d = it if order == 'orig' else dict(it, A=it['B'], B=it['A'], expected_winner='B' if it['expected_winner'] == 'A' else 'A')
                jobs.append(dict(phase='pairwise', id=it['id'], order=order, expected=d['expected_winner'], sys=ps, user=rj.fill(pu, d)))
        if 'single' in phases:
            for side in 'AB':
                good = side == it['expected_winner']
                jobs.append(dict(phase='single', id=it['id'], order=side, side_is='compliant' if good else 'violating', expected='pass' if good else 'fail',
                                 sys=ss, user=rj.fill(su, dict(it, text=it[side]))))
    model = opts['model']; ms = rj.models(); pin, pout = rj.price(ms[model]) if model in ms else (0, 0)
    J = rj.Judge(CFG['judge']['backend'], model, (pin, pout), 1e9); J.max_tokens = CFG['judge']['max_tokens']
    key = lambda j: llm.Cache.key(model, [{'role': 'system', 'content': j['sys']}, {'role': 'user', 'content': j['user']}], t=0, mt=J.max_tokens)
    unc = [j for j in jobs if J.cache.get(key(j)) is None]
    proj = sum(len(j['sys']) + len(j['user']) for j in unc) / 3.5 * pin + len(unc) * 400 * pout
    cap = CFG['budget']['phase_cap_usd']; spent = spend()['total_usd']
    if spent + proj > cap: raise SystemExit(f'BUDGET: projected ${proj:.3f} on top of ${spent:.3f} spent exceeds phase cap ${cap}')
    J.cap = cap - spent
    res = rj.run(J, jobs, CFG['judge']['workers'])
    total = add_spend(J.cost, f'judge {label}: {len(unc)} new calls, {len(jobs) - len(unc)} cached') if J.cost else spend()['total_usd']
    meta = {it['id']: it for it in items}
    for r in res:
        it = meta[r['id']]; r.update(kind=it['kind'], rule_id=it['rule_id'], family=it['rule_family'], check_type=it['rule_check_type'], split=it['split'])
    return res, dict(model=model, calls=len(unc), cached=len(jobs) - len(unc), cost=round(J.cost, 5), phase_spend_total=total)
# ---------------------------------------------------------------- deterministic
def det_metrics(split):
    subprocess.run([sys.executable, rel('evals', 'run_deterministic.py')], check=True, capture_output=True)
    d = json.load(open(rel('evals', 'det_results.json'))); S = json.load(open(path('splits')))['case_split']
    insplit = lambda cid: S.get(cid.replace('CTRL-', ''), 'dev') == split
    claim = [k for k, v in d['per_check'].items() if v['group'] == 'claim_level']
    fired = sum(1 for k in claim for c in d['per_check'][k]['cases_fired'] if insplit(c)); missed = sum(1 for k in claim for c in d['per_check'][k]['cases_missed'] if insplit(c))
    ctrl = [r for r in d['controls']['rows'] if insplit(r['control_id'])]
    claim_set = set(claim)
    t_ev = sum(1 for v in d['controls']['targeted'].values() for c in v.get('controls_evaluated', []) if insplit(c))
    t_f = sum(1 for v in d['controls']['targeted'].values() for c in v['controls_fired'] if insplit(c))
    return dict(claim_level_recall=_r(fired, fired + missed), recall_n=fired + missed,
                controls=len(ctrl), control_any_claim_level_fire_rate=_r(sum(1 for r in ctrl if set(r['failed_checks']) & claim_set), len(ctrl)),
                targeted_fp_rate=_r(t_f, t_ev), targeted_n=t_ev)
def _r(a, b): return round(a / b, 4) if b else None
# ---------------------------------------------------------------- scoring
def judge_metrics(res, split=None):
    rs = [r for r in res if split is None or r['split'] == split]
    def single(sub):
        v = [r for r in sub if r['phase'] == 'single' and r.get('out') and r['out'].get('verdict') in ('pass', 'fail')]
        pos = [r for r in v if r['side_is'] == 'violating']; neg = [r for r in v if r['side_is'] == 'compliant']
        sens = _r(sum(r['out']['verdict'] == 'fail' for r in pos), len(pos)); spec = _r(sum(r['out']['verdict'] == 'pass' for r in neg), len(neg))
        ba = round((sens + spec) / 2, 4) if sens is not None and spec is not None else None
        return dict(sensitivity=sens, specificity=spec, balanced_accuracy=ba, n_pos=len(pos), n_neg=len(neg))
    def pair(sub):
        v = [r for r in sub if r['phase'] == 'pairwise' and r.get('out') and r['out'].get('winner') in ('A', 'B')]
        a = [r for r in v if r['expected'] == 'A']; b = [r for r in v if r['expected'] == 'B']
        byid = collections.defaultdict(dict)
        for r in v: byid[r['id']][r['order']] = r['out']['winner'] == r['expected']
        both = [x for x in byid.values() if len(x) == 2]
        return dict(accuracy=_r(sum(r['out']['winner'] == r['expected'] for r in v), len(v)), n=len(v),
                    acc_when_A=_r(sum(r['out']['winner'] == 'A' for r in a), len(a)), acc_when_B=_r(sum(r['out']['winner'] == 'B' for r in b), len(b)),
                    order_flips=sum(x['orig'] != x['swapped'] for x in both), pairs_both_orders=len(both))
    m = dict(single=single(rs), single_easy=single([r for r in rs if r['kind'] == 'easy']), single_near_miss=single([r for r in rs if r['kind'] == 'near_miss']),
             pairwise=pair(rs), pairwise_easy=pair([r for r in rs if r['kind'] == 'easy']), pairwise_near_miss=pair([r for r in rs if r['kind'] == 'near_miss']),
             unparseable=sum(1 for r in rs if not r.get('out')))
    m['by_family'] = {f: single([r for r in rs if r['family'] == f]) for f in 'ABCDE' if any(r['family'] == f for r in rs)}
    m['by_check_type'] = {c: single([r for r in rs if r['check_type'] == c]) for c in ('deterministic', 'judgment')}
    return m
def coverage(items):
    rules = load_rules(); cases = load_jsonl(path('cases')); ctrls = load_jsonl(path('controls'))
    ctrl_cases = {k['source_case_id'] for k in ctrls}; pos = collections.defaultdict(int); neg = collections.defaultdict(int)
    for r in rules.values():
        for cid in r['opdp_case_ids']:
            pos[r['id']] += 1
            if cid in ctrl_cases: neg[r['id']] += 1
    for it in items: pos[it['rule_id']] += 1; neg[it['rule_id']] += 1
    both = [rid for rid in rules if pos[rid] and neg[rid]]
    return dict(rules=len(rules), with_positive=sum(1 for r in rules if pos[r]), with_pos_and_neg=len(both), missing=sorted(set(rules) - set(both)))
def scoreboard(items, res, jmeta, label):
    sb = dict(label=label, at=now(), judge_model=jmeta.get('model'), cost_this_score=jmeta.get('cost'), phase_spend_total=spend()['total_usd'],
              items=dict(collections.Counter(f"{i['kind']}/{i['split']}" for i in items)), coverage=coverage(items))
    for sp in ('dev', 'holdout'): sb[sp] = dict(judge=judge_metrics(res, sp), det=det_metrics(sp))
    return sb
# ---------------------------------------------------------------- acceptance
def noise(p, n, floor_items=None):
    floor_items = floor_items or CFG['loop']['noise_floor_items']
    if not n or p is None: return 1.0
    return max(floor_items / n, math.sqrt(max(p * (1 - p), 1e-9) / n))
def metric(sb, split, name):
    j = sb[split]['judge']
    return dict(judge_balanced_accuracy=j['single']['balanced_accuracy'], single_sensitivity=j['single']['sensitivity'], single_specificity=j['single']['specificity'],
                pairwise_accuracy=j['pairwise']['accuracy'], near_miss_balanced_accuracy=j['single_near_miss']['balanced_accuracy'])[name]
EPS = 2e-4  # metrics are stored rounded to 4 decimals; without this a drop of exactly 1 item (= the noise floor) can read as 0.0084 > 0.0083
def accept(before, after, target):
    """Accept iff (1) target metric improves on dev, (2) dev balanced accuracy doesn't regress beyond noise,
    (3) holdout balanced accuracy and pairwise accuracy don't regress beyond noise, (4) no dev rule-family slice drops beyond noise,
    (5) [added round 2] neither dev single-item sensitivity nor specificity drops by more than 2x noise: balanced accuracy can hide
    a trade of recall for specificity, and for a pre-review tool missed violations are the costly error."""
    why = []; ok = True
    d_t = (metric(after, 'dev', target) or 0) - (metric(before, 'dev', target) or 0)
    if d_t <= 0: ok = False; why.append(f'dev {target} did not improve ({d_t:+.4f})')
    for sp, name in (('dev', 'judge_balanced_accuracy'), ('holdout', 'judge_balanced_accuracy'), ('holdout', 'pairwise_accuracy')):
        b, a = metric(before, sp, name), metric(after, sp, name)
        n = (min(before[sp]['judge']['single']['n_pos'], before[sp]['judge']['single']['n_neg']) if 'balanced' in name else before[sp]['judge']['pairwise']['n'])
        if b is not None and a is not None and a - b < -noise(b, n) - EPS: ok = False; why.append(f'{sp} {name} regressed {a - b:+.4f} (noise {noise(b, n):.4f})')
    for f, sb in before['dev']['judge']['by_family'].items():
        sa = after['dev']['judge']['by_family'].get(f)
        n = min(sb['n_pos'], sb['n_neg'])
        if sa and n >= CFG['loop']['min_slice_n'] and sb['balanced_accuracy'] is not None and sa['balanced_accuracy'] is not None \
           and sa['balanced_accuracy'] - sb['balanced_accuracy'] < -noise(sb['balanced_accuracy'], n) - EPS:
            ok = False; why.append(f'dev family {f} dropped {sa["balanced_accuracy"] - sb["balanced_accuracy"]:+.4f}')
    for name, nk in (('single_sensitivity', 'n_pos'), ('single_specificity', 'n_neg')):
        b, a = metric(before, 'dev', name), metric(after, 'dev', name); n = before['dev']['judge']['single'][nk]
        if b is not None and a is not None and a - b < -2 * noise(b, n) - EPS: ok = False; why.append(f'dev {name} dropped {a - b:+.4f} (> 2x noise {2 * noise(b, n):.4f})')
    if ok: why.append(f'dev {target} {d_t:+.4f}; no holdout/slice/sens-spec regression beyond noise')
    return ok, '; '.join(why)
def deltas(before, after):
    out = {}
    for sp in ('dev', 'holdout'):
        for name in ('judge_balanced_accuracy', 'single_sensitivity', 'single_specificity', 'pairwise_accuracy', 'near_miss_balanced_accuracy'):
            b, a = metric(before, sp, name), metric(after, sp, name)
            out[f'{sp}.{name}'] = dict(before=b, after=a, delta=None if a is None or b is None else round(a - b, 4))
    return out
def ledger(row):
    row = dict(at=now(), **row)
    with open(path('ledger'), 'a') as f: f.write(json.dumps(row, ensure_ascii=False) + '\n')
    return row
