"""Generates SYNTHETIC compliant rewrites (negative controls) for every judgment case and a seeded stratified sample of
deterministic cases. Drafts are LLM-generated from the letter's own rationale, cached in evals/controls_raw.jsonl
(so rebuilds do not re-call the API), then assembled into evals/controls.jsonl with a check-ready `piece`.
Every record: synthetic=true, generator=<model>, human_reviewed=false."""
import json, os, re, sys, random, collections, concurrent.futures as cf
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0] = [B, f'{B}/evals', f'{B}/judge']
from fixtures import case_fixture
import llm
from controls_manual import M as MANUAL
MODEL = 'grok-4.20-0309-reasoning'; RAW = f'{B}/evals/controls_raw.jsonl'; N_DET = 40
SYS = """You write SYNTHETIC negative controls for an eval of a pharma promotional-review (MLR) tool.
Given an FDA OPDP finding, write a compliant rewrite of the cited promotional content that:
- keeps the same drug, piece type, audience and general message;
- fixes ONLY the problem FDA cited, using FDA's own rationale as the guide (e.g., add the omitted limitation/risk, swap the misleading endpoint for a label-supported framing, add absolute risk next to relative risk, remove 'well tolerated' and state the actual adverse-reaction profile);
- does NOT invent specific numbers, study results, or label text that are not in the provided material. Where label content is needed and not provided, insert a bracketed placeholder such as [boxed warning text from PI] or [ORR % and 95% CI from PI Section 14];
- for visual/audiovisual problems, write a short bracketed SYNTHETIC presentation note describing the compliant presentation (e.g., [VISUAL: risk supers on screen, no competing graphics; risk narrated at same pace as benefits]);
- if the claim cannot be made compliantly at all (e.g., promoting an unapproved use), the rewrite should be the closest compliant alternative (e.g., the on-label statement) and say so in change_summary.
Return JSON: {"rewrite_text": str, "change_summary": str, "fixed_problem": str, "context_needed": "none"|"pi_text"|"asset_visuals"|"study_data", "residual_uncertainty": str}
context_needed = what a reviewer would need beyond the text to confirm the rewrite is compliant."""
NOTE_RX = re.compile(r'\[(VISUAL|SYNTHETIC|AUDIO|BOOTH|PRESENTATION|NOTE)\b', re.I)
def strip_notes(t):
    """Remove bracketed synthetic presentation/editorial notes (balanced brackets); keep [placeholder from PI] tokens."""
    while (m := NOTE_RX.search(t)):
        depth, i = 0, m.start()
        for j in range(m.start(), len(t)):
            depth += (t[j] == '[') - (t[j] == ']')
            if depth == 0: i = j; break
        else: i = len(t) - 1
        t = t[:m.start()] + ' ' + t[i + 1:]
    return re.sub(r'\s+', ' ', t).strip()
def prompt(c):
    return (f"Drug: {c['product']}\nPiece type: {c['piece_type']} | Audience: {c['audience']}\nFDA category: {c['category']} | Heading: {c['letter_heading']}\n"
            f"Cited content (as quoted/described in the letter):\n{c['claim_text']}\n\nContext: {c.get('context','')}\n\nFDA rationale: {c['fda_rationale']}\nRegulation: {c['regulation']}")
def select(cases):
    jud = [c for c in cases if c['check_type'] == 'judgment']
    det = [c for c in cases if c['check_type'] == 'deterministic']
    by = collections.defaultdict(list)
    for c in det: by[c['category']].append(c)
    rng = random.Random(7); pick = []
    quota = {k: max(1, round(N_DET * len(v) / len(det))) for k, v in by.items()}
    for k, v in sorted(by.items()): pick += rng.sample(v, min(quota[k], len(v)))
    return jud + sorted(pick, key=lambda c: c['id'])
def main():
    cases = [json.loads(l) for l in open(f'{B}/evals/opdp_cases.jsonl')]
    sel = select(cases)
    raw = {json.loads(l)['case_id']: json.loads(l) for l in open(RAW)} if os.path.exists(RAW) else {}
    todo = [c for c in sel if c['id'] not in raw and c['id'] not in MANUAL]
    if todo and not llm.available(): print('XAI_API_KEY missing: cannot generate', len(todo), 'controls'); 
    elif todo:
        def gen(c):
            out = llm.chat([{'role': 'system', 'content': SYS}, {'role': 'user', 'content': prompt(c)}], MODEL, max_tokens=3000, json_mode=True)
            return dict(case_id=c['id'], model=MODEL, output=json.loads(out))
        with cf.ThreadPoolExecutor(8) as ex, open(RAW, 'a') as f:
            for fut in cf.as_completed([ex.submit(gen, c) for c in todo]):
                try: r = fut.result(); print('ok', r['case_id'], flush=True); raw[r['case_id']] = r; f.write(json.dumps(r, ensure_ascii=False) + '\n'); f.flush()
                except Exception as e: print('gen error', type(e).__name__, str(e)[:200], flush=True)
    out = []
    for c in sel:
        if c['id'] in raw: o = raw[c['id']]['output']; gen_by = 'llm:' + raw[c['id']]['model']
        elif c['id'] in MANUAL:
            t, cs, cn = MANUAL[c['id']]; o = dict(rewrite_text=t, change_summary=cs, fixed_problem=c['fda_rationale'], context_needed=cn, residual_uncertainty=None); gen_by = 'agent-authored'
        else: continue
        fx = case_fixture(c); fx.pop('_missing_quoted', None)
        # piece text = rewrite minus synthetic presentation notes (they describe visuals/process, not on-piece text)
        fx['text'] = strip_notes(o['rewrite_text'])
        fx['meta'].pop('endpoint_status', None)  # rewrites replace the exploratory/post hoc claim; the original's endpoint status no longer describes the text
        if c['category'].startswith('Failure to submit'): fx['meta']['form_2253_id'] = 'SYNTHETIC-2253'
        out.append(dict(id='CTRL-' + c['id'], synthetic=True, generator=gen_by, human_reviewed=False,
                        source_case_id=c['id'], source_check_type=c['check_type'], category=c['category'], product=c['product'],
                        piece_type=c['piece_type'], audience=c['audience'], original_claim=c['claim_text'], compliant_rewrite=o['rewrite_text'],
                        change_summary=o.get('change_summary'), fixed_problem=o.get('fixed_problem'), context_needed=o.get('context_needed'),
                        residual_uncertainty=o.get('residual_uncertainty'), source_url=c['source_url'], piece=fx))
    # eval-data layer, applied in this order (each logged in evals/ledger.jsonl as an eval_data change):
    #  1. de-placeholdered rewrites (evals/controls_rewrites_v2.jsonl, built by evals/deplaceholder.py)
    #  2. hand fixes (controls_manual.CONTROL_FIXES), which win over everything
    v2p = f'{B}/evals/controls_rewrites_v2.jsonl'
    v2 = {json.loads(l)['control_id']: json.loads(l) for l in open(v2p)} if os.path.exists(v2p) else {}
    from controls_manual import CONTROL_FIXES
    for r in out:
        r['compliant_rewrite_v1'] = r['compliant_rewrite']
        if r['id'] in v2 and v2[r['id']].get('accepted'):
            r['compliant_rewrite'] = v2[r['id']]['rewrite_text']; r['generator'] += '+deplaceholder:' + v2[r['id']]['model']
        if r['id'] in CONTROL_FIXES:
            r['compliant_rewrite'] = CONTROL_FIXES[r['id']]['text']; r['generator'] += '+hand_fix'; r['fix_note'] = CONTROL_FIXES[r['id']]['why']
        if r['compliant_rewrite'] != r['compliant_rewrite_v1']: r['piece']['text'] = strip_notes(r['compliant_rewrite'])
    with open(f'{B}/evals/controls.jsonl', 'w') as f:
        for r in out: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('controls', len(out), dict(collections.Counter((r['source_check_type'], r['generator']) for r in out)))
if __name__ == '__main__': main()
