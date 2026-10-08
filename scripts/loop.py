"""One command for the self-improvement loop:  python3 scripts/loop.py --round N
Steps (each writes a reviewable file):
  1. SCORE     current accepted state on dev + holdout  -> evals/scoreboard/round_N_baseline.{json,md}
  2. TRIAGE    every DEV failure gets one root-cause label + layer (heuristics first, LLM proposes the rest)
                                                         -> evals/triage/round_N.jsonl   (review_status: unreviewed)
  3. PROPOSE   candidate changes grouped by layer       -> loop/proposals/round_N.json  (approved: false unless --auto-approve)
  4. EVALUATE  each APPROVED variant change vs the acceptance rule (dev improves, holdout/slices don't regress beyond noise)
                                                         -> evals/ledger.jsonl, loop/state.json
  5. SCOREBOARD final                                    -> evals/scoreboard/round_N.{json,md}
Human-in-the-loop: rule_text and eval_data proposals are NEVER auto-approved; set "approved": true (and your name in
"approved_by") in the proposals file after reading them, then rerun with --evaluate-only. judge_prompt and rule_assignment
proposals can be auto-approved with --auto-approve (still logged). Holdout results are never shown to triage/proposal steps.
Flags: --legacy-baseline (round 0: score the pre-loop pipeline as it was), --no-propose, --evaluate-only, --auto-approve."""
import os, sys, json, argparse, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, rel, path, load_jsonl, write_jsonl, load_rules
import engine as E
sys.path[:0] = [rel('evals'), rel('judge')]
from make_pairwise import build_items
LAYERS = ['rule_text', 'rule_assignment', 'eval_data', 'det_check', 'judge_prompt', 'judge_model', 'input_gap']
def sb_md(sb):
    L = [f"# Scoreboard: {sb['label']}", "", f"Generated {sb['at']}. Judge model `{sb['judge_model']}`. Phase spend so far ${sb['phase_spend_total']:.4f}. Items {sb['items']}.", "",
         "| Metric | dev | holdout |", "|---|---|---|"]
    def g(sp, *ks):
        x = sb[sp]
        for k in ks: x = x.get(k) if isinstance(x, dict) else None
        return '—' if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))
    rows = [('Judge single-item sensitivity (violating → fail)', ('judge', 'single', 'sensitivity')), ('Judge single-item specificity (compliant → pass)', ('judge', 'single', 'specificity')),
            ('Judge balanced accuracy (primary)', ('judge', 'single', 'balanced_accuracy')), ('  near-miss balanced accuracy', ('judge', 'single_near_miss', 'balanced_accuracy')),
            ('  easy balanced accuracy', ('judge', 'single_easy', 'balanced_accuracy')), ('Pairwise accuracy (both orders)', ('judge', 'pairwise', 'accuracy')),
            ('  pairwise near-miss accuracy', ('judge', 'pairwise_near_miss', 'accuracy')), ('Position: acc when correct=A', ('judge', 'pairwise', 'acc_when_A')),
            ('Position: acc when correct=B', ('judge', 'pairwise', 'acc_when_B')), ('Position: order flips (pairs)', ('judge', 'pairwise', 'order_flips')),
            ('Det claim-level recall (letter cases)', ('det', 'claim_level_recall')), ('Det targeted FP rate (controls)', ('det', 'targeted_fp_rate')),
            ('Det any claim-level fire on controls', ('det', 'control_any_claim_level_fire_rate')), ('Unparseable judge answers', ('judge', 'unparseable'))]
    for name, ks in rows: L.append(f"| {name} | {g('dev', *ks)} | {g('holdout', *ks)} |")
    L += ["", "By rule family (dev, single-item balanced accuracy / n_pos / n_neg): " + '; '.join(f"{f}: {v['balanced_accuracy']} ({v['n_pos']}/{v['n_neg']})" for f, v in sb['dev']['judge']['by_family'].items()),
          "By check_type (dev): " + '; '.join(f"{k}: {v['balanced_accuracy']}" for k, v in sb['dev']['judge']['by_check_type'].items()),
          f"Coverage: {sb['coverage']['with_pos_and_neg']}/{sb['coverage']['rules']} rules have ≥1 positive and ≥1 negative case; missing: {', '.join(sb['coverage']['missing']) or 'none'}.", ""]
    return '\n'.join(L) + '\n'
def save_sb(sb, name):
    d = rel(CFG['paths']['scoreboard_dir']); os.makedirs(d, exist_ok=True)
    json.dump(sb, open(f'{d}/{name}.json', 'w'), indent=1); open(f'{d}/{name}.md', 'w').write(sb_md(sb))
def score(opts, label, legacy=False):
    items = build_items(dict(opts, include_nm2=not legacy))
    res, jm = E.judge_items(items, opts, label=label)
    write_jsonl(rel('judge', 'results', f'loop_{re.sub(r"[^A-Za-z0-9_.-]", "_", label)}.jsonl'), res)
    return E.scoreboard(items, res, jm, label), items, res
# ---------------------------------------------------------------- triage (DEV ONLY)
TRIAGE_SYS = """You triage failures of an LLM judge used for pharma promotional (MLR) pre-review evals. For ONE failure, choose exactly one root-cause LAYER:
rule_text (the rule's wording is wrong/incomplete for this item), rule_assignment (the item is being judged against the wrong rule), eval_data (the synthetic item/rewrite/expected label is wrong or leaks the answer),
judge_prompt (judge applied the rule too strictly or too leniently; fixable by guidance), judge_model (inconsistent/careless reasoning a prompt is unlikely to fix, e.g. position flips), input_gap (needs visuals/PI/study data not provided).
Return JSON {"layer": one of the six, "root_cause": short snake_case label, "direction": "too_strict"|"too_lenient"|"n/a", "rationale": one sentence}."""
def triage(rnd, items, res):
    import llm
    meta = {i['id']: i for i in items}; rows = []
    dev = [r for r in res if r['split'] == 'dev' and r.get('out')]
    by = collections.defaultdict(list)
    for r in dev: by[(r['id'], r['phase'])].append(r)
    pend = []
    for (iid, ph), rs in by.items():
        it = meta[iid]
        if ph == 'single':
            for r in rs:
                if r['out'].get('verdict') == r['expected']: continue
                text = it['A'] if r['order'] == 'A' else it['B']
                f = dict(failure_id=f"R{rnd}-{iid}-single-{r['order']}", mode='single', item=iid, kind=it['kind'], rule_id=it['rule_id'], side=r['side_is'],
                         expected=r['expected'], got=r['out'].get('verdict'), judge_reason=(r['out'].get('reason') or '')[:400], missing_context=r['out'].get('missing_context'))
                if r['side_is'] == 'compliant' and re.search(r'\[(?!Visual\])', text):
                    f.update(layer='eval_data', root_cause='placeholder_leakage', direction='n/a', proposed_by='heuristic', rationale='compliant text still contains bracketed placeholders')
                elif it['kind'] == 'easy' and r['out'].get('missing_context') and it.get('context_needed') in ('asset_visuals', 'study_data'):
                    f.update(layer='input_gap', root_cause='needs_' + it['context_needed'], direction='n/a', proposed_by='heuristic', rationale='judge flagged missing context and the item needs data we do not have')
                else: pend.append((f, it, text))
                rows.append(f)
        else:
            wrong = [r for r in rs if r['out'].get('winner') != r['expected']]
            if not wrong: continue
            f = dict(failure_id=f"R{rnd}-{iid}-pairwise", mode='pairwise', item=iid, kind=it['kind'], rule_id=it['rule_id'], orders_wrong=[r['order'] for r in wrong],
                     judge_reason=(wrong[0]['out'].get('reason') or '')[:400])
            if len(wrong) == 1: f.update(layer='judge_model', root_cause='position_sensitive', direction='n/a', proposed_by='heuristic', rationale='wrong in only one A/B order')
            else: pend.append((f, it, None))
            rows.append(f)
    model = E.load_state().get('model') or CFG['judge']['model']; cost = [0.0]
    import concurrent.futures as cf, threading; lock = threading.Lock()
    def one(args):
        f, it, text = args
        u = (f"Rule {it['rule_id']}: {it['rule_text']}\nQuestion: {it['rule_question']}\nItem kind: {it['kind']} | letter category: {it.get('category')}\nLabel facts: {it['label_facts'][:600]}\n"
             f"Why the pair differs (author note): {it.get('why', 'n/a')}\nMode: {f['mode']}; expected {f.get('expected', 'compliant side wins')}, judge said {f.get('got', 'the violating side')}\n"
             f"Text judged: {(text or (it['A'] + ' ||| ' + it['B']))[:1500]}\nJudge reason: {f['judge_reason']}")
        try:
            r = llm.chat_full([{'role': 'system', 'content': TRIAGE_SYS}, {'role': 'user', 'content': u}], model, CFG['judge']['backend'], temperature=0, max_tokens=1500, json_mode=True)
            with lock: cost[0] += float((r.get('usage') or {}).get('cost') or 0)
            content = r['choices'][0]['message'].get('content') or ''
            m = re.search(r'\{.*\}', content, re.S)
            if not m: raise ValueError(f"no JSON in reply (finish={r['choices'][0].get('finish_reason')})")
            o = json.loads(m.group(0))
            f.update(layer=o.get('layer') if o.get('layer') in LAYERS else 'judge_prompt', root_cause=o.get('root_cause'), direction=o.get('direction'), rationale=o.get('rationale'), proposed_by='llm:' + model)
        except Exception as e:
            f.update(layer='judge_prompt', root_cause='unclassified', direction='n/a', rationale=f'triage call failed: {str(e)[:80]}', proposed_by='fallback')
    with cf.ThreadPoolExecutor(CFG['judge']['workers']) as ex: list(ex.map(one, pend))
    cost = cost[0]
    if cost: E.add_spend(cost, f'triage round {rnd}')
    # deterministic failures (dev cases only)
    d = json.load(open(rel('evals', 'det_results.json'))); S = json.load(open(path('splits')))['case_split']
    for chk, v in d['per_check'].items():
        if v['group'] != 'claim_level': continue
        for cid in v['cases_missed']:
            if S.get(cid) == 'dev': rows.append(dict(failure_id=f'R{rnd}-det-{chk}-{cid}', mode='det_recall', item=cid, rule_id=chk, layer='det_check', root_cause='lexicon_or_logic_miss', proposed_by='heuristic', rationale='claim-level check did not fire on a letter-cited case'))
        if v['needs_input']: rows.append(dict(failure_id=f'R{rnd}-det-{chk}-needs_input', mode='det_recall', item=f'{v["needs_input"]} cases (all splits)', rule_id=chk, layer='input_gap', root_cause='needs_input', proposed_by='heuristic', rationale='letter text cannot supply what the check needs'))
    for chk, v in d['controls']['targeted'].items():
        for cid in v['controls_fired']:
            if S.get(cid.replace('CTRL-', '')) == 'dev': rows.append(dict(failure_id=f'R{rnd}-det-fp-{chk}-{cid}', mode='det_fp', item=cid, rule_id=chk, layer='det_check', root_cause='fires_on_compliant_control', proposed_by='heuristic', rationale='check still fires on the rewrite that fixed its problem; review whether the check or the rewrite is wrong'))
    for f in rows: f.update(review_status='unreviewed', reviewer=None, final_layer=None)
    write_jsonl(rel('evals', 'triage', f'round_{rnd}.jsonl'), rows)
    return rows
# ---------------------------------------------------------------- proposals
def propose(rnd, rows, items):
    import llm
    meta = {i['id']: i for i in items}; props = []; st = E.load_state(); model = st.get('model') or CFG['judge']['model']; cost = 0.0
    jp = collections.defaultdict(list)
    for f in rows:
        if f['layer'] != 'judge_prompt' or f.get('root_cause') == 'unclassified' and f.get('mode') != 'single': continue
        d = f.get('direction') if f.get('direction') in ('too_strict', 'too_lenient') else ({'compliant': 'too_strict', 'violating': 'too_lenient'}.get(f.get('side')))
        if d: jp[d].append(f)
    for direction, fs in jp.items():
        if len(fs) < 2: continue
        u = "Write ONE short, general guidance bullet (max 45 words) for an MLR review judge that would fix this pattern without naming specific products. Failures (judge was " + direction + "):\n" + \
            '\n'.join(f"- rule {f['rule_id']}: {f['judge_reason'][:250]}" for f in fs[:8]) + '\nReturn JSON {"text": str}'
        try:
            r = llm.chat_full([{'role': 'user', 'content': u}], model, CFG['judge']['backend'], temperature=0, max_tokens=1500, json_mode=True)
            cost += float((r.get('usage') or {}).get('cost') or 0)
            text = json.loads(re.search(r'\{.*\}', r['choices'][0]['message'].get('content') or '', re.S).group(0))['text']
            props.append(dict(id=f'P{rnd}-judge-{direction}', layer='judge_prompt', type='judge_addendum', payload=dict(text=text), target_metric='single_specificity' if direction == 'too_strict' else 'single_sensitivity',
                              hypothesis=f'judge is {direction} on {len(fs)} dev failures', evidence=[f['failure_id'] for f in fs], requires_human=False, approved=False))
        except Exception as e: print('proposal draft failed', e)
    ra = [f for f in rows if f['layer'] == 'rule_assignment']
    if len(ra) >= 2 and not any(c['type'] == 'pair_rule_assignment' for c in st['accepted']):
        props.append(dict(id=f'P{rnd}-rule-assignment', layer='rule_assignment', type='pair_rule_assignment', payload=dict(mode='category_match'), target_metric='judge_balanced_accuracy',
                          hypothesis=f'{len(ra)} dev failures judged against the wrong rule', evidence=[f['failure_id'] for f in ra], requires_human=False, approved=False))
    rt = collections.defaultdict(list)
    for f in rows:
        if f['layer'] == 'rule_text': rt[f['rule_id']].append(f)
    for rid, fs in rt.items():
        props.append(dict(id=f'P{rnd}-ruletext-{rid}', layer='rule_text', type='rule_override', payload=dict(rule_id=rid, rule_text='<HUMAN: write corrected rule text citing the source section>'),
                          target_metric='judge_balanced_accuracy', hypothesis=f'rule {rid} wording is incomplete for {len(fs)} dev failures', evidence=[f['failure_id'] for f in fs], requires_human=True, approved=False))
    for layer in ('eval_data', 'det_check', 'input_gap', 'judge_model'):
        fs = [f for f in rows if f['layer'] == layer]
        if fs: props.append(dict(id=f'P{rnd}-{layer}', layer=layer, type='manual', payload=dict(items=[f['failure_id'] for f in fs][:60], count=len(fs)),
                                 hypothesis=f'{len(fs)} dev failures attributed to {layer}', requires_human=True, approved=False,
                                 instructions={'eval_data': 'Fix the listed items in the eval files; log with loop.py --log-eval-data; re-baseline.', 'det_check': 'Edit checks/margin_checks.py; re-run; the loop re-scores det metrics.',
                                               'input_gap': 'Acquire the missing inputs (assets, PI, study data) or accept as a known limit.', 'judge_model': 'Consider a stronger model (budget) or majority vote over both orders.'}[layer]))
    if cost: E.add_spend(cost, f'proposal drafting round {rnd}')
    return props
# ---------------------------------------------------------------- evaluate
def evaluate(rnd, props_path, base_sb, auto_approve=False):
    P = json.load(open(props_path)); st = E.load_state(); results = []
    for p in P['proposals']:
        if p['type'] == 'manual' or p.get('evaluated'): continue
        if auto_approve and not p['requires_human'] and p['layer'] in ('judge_prompt', 'rule_assignment') and not p.get('approved'):
            p['approved'] = True; p['approved_by'] = 'auto (--auto-approve; low-risk layer)'
        if not p.get('approved'): continue
        if p['layer'] == 'rule_text' and '<HUMAN' in json.dumps(p['payload']): continue
        change = dict(id=p['id'], type=p['type'], payload=p['payload'], layer=p['layer'])
        opts = E.active_opts([change])
        try: after, items, res = score(opts, f'round{rnd}-{p["id"]}')
        except SystemExit as e: p['evaluated'] = True; p['result'] = f'not evaluated: {e}'; print(e); break
        ok, why = E.accept(base_sb, after, p.get('target_metric', 'judge_balanced_accuracy'))
        status = ('accepted_pending_human_review' if p['requires_human'] else 'accepted') if ok else 'rejected'
        E.ledger(dict(round=rnd, change_id=p['id'], kind='variant', layer=p['layer'], hypothesis=p['hypothesis'], change=change, target_metric=p.get('target_metric'),
                      metrics=E.deltas(base_sb, after), decision=status, reason=why, approved_by=p.get('approved_by'), cost_usd=after['cost_this_score'],
                      judge_results=f"judge/results/loop_round{rnd}-{p['id']}.jsonl"))
        p['evaluated'] = True; p['result'] = status; p['reason'] = why; results.append((p['id'], status, why))
        print(p['id'], status, '|', why)
        if ok:
            st = E.load_state(); st['accepted'].append(dict(change, round=rnd, status=status)); E.save_state(st); base_sb = after
    json.dump(P, open(props_path, 'w'), indent=1)
    return base_sb, results
def log_eval_data(rnd, cid, desc, files, legacy, reviewer):
    """Eval-data changes edit the TEST, so they are never 'accepted' on metrics: we re-score, log before/after for transparency,
    and the new numbers become the baseline. Label/rewrite edits need a named human (or the owner's explicit request) in --reviewer."""
    st = E.load_state(); bp = st.get('last_scoreboard')
    before = json.load(open(rel(bp))) if bp else None
    after, _, _ = score(E.active_opts(), f'round{rnd}-evaldata-{cid}', legacy=legacy)
    name = f'round_{rnd}_evaldata_{cid}'; save_sb(after, name)
    E.ledger(dict(round=rnd, change_id=cid, kind='eval_data', layer='eval_data', hypothesis=desc, files=files, metrics=E.deltas(before, after) if before else None,
                  decision='re-baselined (eval-data change; not judged by the acceptance rule)', reviewed_by=reviewer, cost_usd=after['cost_this_score'],
                  items=after['items']))
    st = E.load_state(); st['last_scoreboard'] = os.path.relpath(rel(CFG['paths']['scoreboard_dir'], name + '.json'), rel()); E.save_state(st)
    print(cid, 'dev BA', after['dev']['judge']['single']['balanced_accuracy'], 'holdout BA', after['holdout']['judge']['single']['balanced_accuracy'], 'spend', E.spend()['total_usd'])
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--round', type=int, required=True); ap.add_argument('--legacy-baseline', action='store_true')
    ap.add_argument('--eval-data', help='log an eval-data change id (re-baseline)'); ap.add_argument('--desc', default=''); ap.add_argument('--files', default='')
    ap.add_argument('--reviewer', default=None, help='who approved the eval-data edit (required for label/rewrite edits)')
    ap.add_argument('--no-propose', action='store_true'); ap.add_argument('--evaluate-only', action='store_true'); ap.add_argument('--auto-approve', action='store_true')
    a = ap.parse_args(); rnd = a.round; opts = E.active_opts()
    if a.eval_data:
        if not a.reviewer: raise SystemExit('eval-data changes need --reviewer (a human, or the owner request that authorized them)')
        return log_eval_data(rnd, a.eval_data, a.desc, [f for f in a.files.split(',') if f], a.legacy_baseline, a.reviewer)
    pp = rel(CFG['paths']['loop_dir'], 'proposals', f'round_{rnd}.json')
    bpath = rel(CFG['paths']['scoreboard_dir'], f'round_{rnd}_baseline.json')
    if a.evaluate_only and os.path.exists(bpath): base = json.load(open(bpath))
    else:
        base, items, res = score(opts, f'round{rnd}-baseline', legacy=a.legacy_baseline); save_sb(base, f'round_{rnd}_baseline')
        print('baseline dev BA', base['dev']['judge']['single']['balanced_accuracy'], 'holdout BA', base['holdout']['judge']['single']['balanced_accuracy'])
        if not a.no_propose:
            rows = triage(rnd, items, res); print('triage rows', len(rows), dict(collections.Counter(r['layer'] for r in rows)))
            props = propose(rnd, rows, items)
            old = json.load(open(pp))['proposals'] if os.path.exists(pp) else []
            keep = {p['id'] for p in old} | {json.dumps([p['type'], p['payload']], sort_keys=True) for p in old}
            props = [p for p in props if json.dumps([p['type'], p['payload']], sort_keys=True) not in keep]
            json.dump(dict(round=rnd, generated=E.now(), note='Set approved=true (and approved_by) to evaluate. rule_text/eval_data need a human.',
                           proposals=old + [p for p in props if p['id'] not in keep]), open(pp, 'w'), indent=1)
    final = base
    if os.path.exists(pp):
        final, results = evaluate(rnd, pp, base, a.auto_approve)
    save_sb(final, f'round_{rnd}')
    st = E.load_state(); st['last_scoreboard'] = os.path.relpath(rel(CFG['paths']['scoreboard_dir'], f'round_{rnd}.json'), rel()); E.save_state(st)
    try: import loop_summary  # writes evals/scoreboard/SUMMARY.md (before vs after + ledger)
    except Exception as e: print('summary failed', e)
    print('final dev BA', final['dev']['judge']['single']['balanced_accuracy'], 'holdout BA', final['holdout']['judge']['single']['balanced_accuracy'], 'phase spend', E.spend()['total_usd'])
if __name__ == '__main__': main()
