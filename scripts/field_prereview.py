"""Field pre-review: run the CURRENT accepted pipeline (deterministic checks + single-item judge with loop addenda/overrides) over real,
unlabeled pieces in pieces/<slug>/ and write pieces/prereview_<slug>.md. Output is PRE-REVIEW FLAGS for a human MLR reviewer:
never an approval, never sent anywhere. Unscored: the field set has no labels until a human adds them.
Usage: python3 scripts/field_prereview.py [slug ...]"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CFG, rel, load_rules
import engine as E
sys.path[:0] = [rel('judge'), rel('checks'), rel('evals')]
from make_pairwise import rule_fields
FIELD_RULES = ['A-202-E5-01', 'A-202-E6-01J', 'A-202-E6-04J', 'A-202-E6-18', 'B-CFL-01']   # judged per chunk
WHOLE_PAGE_RULES = {'DTC': ['A-202-E7-08', 'E-DTC-14'], 'HCP': ['A-202-E7-08']}             # need the whole page (risk balance)
CHUNK = 24000
def norm(s): return re.sub(r'\s+', ' ', re.sub(r'[“”]', '"', re.sub(r"[‘’]", "'", s or ''))).strip().lower()
def chunks(t):
    out, i = [], 0
    while i < len(t):
        j = min(len(t), i + CHUNK); k = t.rfind('\n', i + CHUNK // 2, j) if j < len(t) else j
        out.append(t[i:(k if k > i else j)]); i = k if k > i else j
    return out
def main(slugs):
    import llm, run_judge as rj, margin_checks as MC
    facts = json.load(open(rel('pieces', 'pi_facts.json'))); rules = load_rules(); opts = E.active_opts()
    manifest = slugs or [d for d in sorted(os.listdir(rel('pieces'))) if os.path.exists(rel('pieces', d, 'page.txt'))]
    ss, su = rj.template('single_prompt.md')
    if opts['addenda']: ss += '\n\nAdditional reviewer guidance (from the improvement loop):\n' + '\n'.join(f'- {a}' for a in opts['addenda'])
    llm.load_openrouter_key(); model = opts['model']; ms = rj.models(); pin, pout = rj.price(ms[model])
    spent = E.spend()['total_usd']; J = rj.Judge(CFG['judge']['backend'], model, (pin, pout), CFG['budget']['phase_cap_usd'] - spent); J.max_tokens = 1200
    pages, jobs = {}, []
    for slug in manifest:
        meta = json.load(open(rel('pieces', slug, 'meta.json'))); text = open(rel('pieces', slug, 'page.txt')).read()
        aud = 'HCP' if 'hcp' in meta['audience'].lower() else 'DTC'; F = facts[meta['brand'].upper()]
        piece = dict(text=text, brand=meta['brand'], established_name=meta['established_name'], audience=aud, piece_type='branded website (homepage)',
                     meta={}, pi=dict(required_risk_terms=F['required_risk_terms'], indication_qualifiers=F['indication_qualifiers']))
        det = [r for r in MC.run_checks(piece) if r['status'] == 'fail']
        pages[slug] = dict(meta=meta, text=text, aud=aud, det=det, F=F)
        base = dict(product=f"{meta['brand']} ({meta['established_name']})", piece_type='Branded website homepage (text capture; visuals not seen)', audience=aud, label_facts=F['label_facts'])
        plan = [(rid, i, c) for i, c in enumerate(chunks(text)) for rid in FIELD_RULES] + [(rid, 'all', text) for rid in WHOLE_PAGE_RULES[aud]]
        for rid, ci, c in plan:
            d = dict(base, **rule_fields(rules[rid], opts['rule_overrides']), text=c)
            jobs.append(dict(phase='single', id=f'{slug}|{rid}|{ci}', order='A', expected=None, sys=ss, user=rj.fill(su, d)))
    proj = sum(len(j['sys']) + len(j['user']) for j in jobs) / 3.5 * pin + len(jobs) * 300 * pout
    if spent + proj > CFG['budget']['phase_cap_usd']: raise SystemExit(f'BUDGET: field pre-review projected ${proj:.3f}')
    res = rj.run(J, jobs, CFG['judge']['workers'])
    if J.cost: E.add_spend(J.cost, f'field pre-review {len(jobs)} calls')
    by = {}
    for r in res: by.setdefault(r['id'].split('|')[0], []).append(r)
    summary = {}
    for slug, P in pages.items():
        flags = []
        for r in by.get(slug, []):
            o = r.get('out') or {}
            if o.get('verdict') != 'fail': continue
            _, rid, ci = r['id'].split('|'); ev = o.get('evidence') or ''
            found = norm(ev.strip('"')) in norm(P['text']) if ev and not ev.lower().startswith('absent') else None
            flags.append(dict(rule_id=rid, chunk=ci, evidence=ev, evidence_verified=found, reason=o.get('reason'), confidence=o.get('confidence'), missing_context=o.get('missing_context')))
        flags.sort(key=lambda f: (f['evidence_verified'] is not True, f['missing_context'] is True, -(f['confidence'] or 0)))
        summary[slug] = dict(judge_flags=flags, det_flags=[dict(rule_id=d['rule_id'], check=d['check'], detail=d['detail'], evidence=[e['text'][:160] for e in d['evidence'][:2]]) for d in P['det']])
        write_md(slug, P, summary[slug], opts)
    json.dump(summary, open(rel('pieces', 'prereview_summary.json'), 'w'), indent=1)
    print('field pre-review done; calls', len(jobs), 'cost', round(J.cost, 4), 'phase spend', E.spend()['total_usd'])
NOTES = json.load(open(rel('pieces', 'prereview_notes.json'))) if os.path.exists(rel('pieces', 'prereview_notes.json')) else {}
def write_md(slug, P, S, opts):
    m = P['meta']; R = load_rules()
    L = [f"# Pre-review flags: {m['brand']} ({m['established_name']}), {m['audience']} homepage", "",
         "> **PRE-REVIEW FLAGS ONLY. NOT AN APPROVAL OR A REGULATORY OPINION.** Generated automatically from a text capture of a public web page. "
         "A qualified human MLR reviewer decides. Nothing here was sent to anyone.", "",
         f"- Source: `{m.get('url_final') or m.get('url_requested')}` captured {m.get('capture_timestamp_pt')} (text in `pieces/{slug}/page.txt`; visuals not reviewed)",
         f"- Pipeline: deterministic checks + single-item judge `{opts['model']}` with {len(opts['addenda'])} loop addenda and {len(opts['rule_overrides'])} rule overrides (state `loop/state.json`)",
         f"- Label facts: `pieces/pi_facts.json` (hand excerpt of `{P['F']['pi_file']}`)", "",
         *( ["## Agent triage notes (top items for the human reviewer; still flags, not findings)", ""] + [f"{i + 1}. {n}" for i, n in enumerate(NOTES.get(slug, []))] + [""] if NOTES.get(slug) else []),
         "## Judge flags (evidence quoted from the page; 'verified' = span found verbatim in page text)", ""]
    if not S['judge_flags']: L.append("None.")
    for f in S['judge_flags']:
        if not f['evidence'] and not f['reason']:
            L.append(f"- {f['rule_id']} chunk {f['chunk']}: judge returned FAIL with no evidence or reason (incomplete output); treat as noise unless a reviewer finds an issue."); continue
        L.append(f"- **{f['rule_id']}** ({R[f['rule_id']]['source']['section']}) chunk {f['chunk']}, confidence {f['confidence']}, "
                 f"evidence {'verified' if f['evidence_verified'] else ('NOT found verbatim' if f['evidence_verified'] is False else 'n/a (absence finding)')}"
                 f"{', judge says missing context' if f['missing_context'] else ''}  \n  Evidence: \"{(f['evidence'] or '')[:300]}\"  \n  Why: {f['reason']}")
    L += ["", "## Deterministic check flags", ""]
    if not S['det_flags']: L.append("None.")
    for d in S['det_flags']: L.append(f"- **{d['rule_id']}** `{d['check']}`: {d['detail']} {('evidence: ' + ' / '.join(repr(e) for e in d['evidence'])) if d['evidence'] else ''}")
    L += ["", "## What a human reviewer should label to turn this into eval cases", "",
          "1. For each flag above: **true issue / false alarm / needs visuals**, with the correct rule id if different. True issues become positive cases; false alarms become negative controls (real compliant text).",
          "2. Pick 3–5 compliant passages (e.g., the ISI block, indication statement) and mark them **compliant**, as real-world negatives for specificity.",
          "3. Record anything the reviewer would flag that the pipeline missed (with the span and rule) → new positive cases and possibly new rules.",
          "4. Confirm the label facts used (`pieces/pi_facts.json`) match the current PI.",
          "5. Note visual-only issues (prominence, placement, ISI tray) separately: they need screenshots and are an input gap for the text judge.", ""]
    open(rel('pieces', f'prereview_{slug}.md'), 'w').write('\n'.join(L))
if __name__ == '__main__': main(sys.argv[1:])
