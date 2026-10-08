"""Margin LLM judge runner (Crosby method, see method.md).
Phases: calibrate (easy pairs with a known winner, both A/B orders) -> nearmiss (27 near-miss pairs, both orders)
-> single (each side of every pair judged alone: would you sign off on this rule as is?).
Backends: openrouter (default; key loaded at runtime from ~/.config/openrouter/api_key, never printed/written) or xai.
Model choice (openrouter): queries /api/v1/models, prefers a capable ':free' model that passes a probe, falls back to a cheap
paid model (< $1/M input tokens) if free models are rate-limited/unreliable. Responses are cached (judge/results/cache.jsonl)
so reruns don't re-spend. Hard spend cap: abort if projected or actual paid cost exceeds --cap (default $3).
Outputs: judge/results/raw.jsonl (all verdicts), judge/results/status.json (model, pricing, cost, summaries)."""
import json, os, sys, re, argparse, collections, concurrent.futures as cf, datetime, urllib.request, urllib.error, threading, time, glob
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f'{B}/judge')
import llm
OUT = f'{B}/judge/results'; os.makedirs(OUT, exist_ok=True)
FREE_PREF = ['nvidia/nemotron-3-ultra-550b-a55b:free', 'google/gemma-4-31b-it:free', 'nvidia/nemotron-3-super-120b-a12b:free', 'thinkingmachines/inkling:free']
PAID_PREF = ['anthropic/claude-haiku-5.5', 'openai/gpt-6-luna', 'qwen/qwen3.8-flash', 'z-ai/glm-5.3-flash', 'xiaomi/mimo-v2.6-flash']
def now(): return datetime.datetime.now().astimezone().isoformat(timespec='seconds')
def template(name):
    t = open(f'{B}/judge/{name}').read().split('\n---\n', 1)[1]
    return t.split('SYSTEM:', 1)[1].split('USER:', 1)[0].strip(), t.split('USER:', 1)[1].strip()
def fill(t, d): return re.sub(r'\{\{(\w+)\}\}', lambda m: str(d.get(m.group(1), '')), t)
def parse(s):
    if not s: return None
    s = re.sub(r'(?s)<think>.*?</think>', '', s)
    for m in re.finditer(r'\{[^{}]*(\{[^{}]*\}[^{}]*)*\}', s):
        try: return json.loads(m.group(0))
        except Exception: continue
    # lenient fallback: models sometimes put unescaped quotes inside "reason"; pull the structured fields by regex
    o = {}
    for k in ('winner', 'verdict'):
        m = re.search(rf'"{k}"\s*:\s*"(\w+)"', s)
        if m: o[k] = m.group(1)
    for k in ('A_approvable', 'B_approvable', 'missing_context'):
        m = re.search(rf'"{k}"\s*:\s*(true|false)', s)
        if m: o[k] = m.group(1) == 'true'
    m = re.search(r'"confidence"\s*:\s*([\d.]+)', s); o.update(confidence=float(m.group(1))) if m else None
    m = re.search(r'"reason"\s*:\s*"(.*)', s, re.S); o.update(reason=m.group(1)[:400], parsed_leniently=True) if m else None
    return o if ('winner' in o or 'verdict' in o) else None
def models():
    return {m['id']: m for m in json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models', timeout=60))['data']}
def price(m): p = m.get('pricing', {}); return float(p.get('prompt') or 0), float(p.get('completion') or 0)
class Judge:
    def __init__(self, backend, model, pricing, cap):
        self.backend, self.model, self.pin, self.pout, self.cap = backend, model, *pricing, cap
        self.cache = llm.Cache(f'{OUT}/cache.jsonl'); self.cost = 0.0; self.lock = threading.Lock(); self.calls = 0; self.cached = 0; self.errors = collections.Counter()
        self.max_tokens = 3000
    def ask(self, sys_t, user_t):
        msgs = [{'role': 'system', 'content': sys_t}, {'role': 'user', 'content': user_t}]
        k = llm.Cache.key(self.model, msgs, t=0, mt=self.max_tokens)
        hit = self.cache.get(k)
        if hit is not None:
            with self.lock: self.cached += 1
            return hit
        with self.lock:
            if self.cost > self.cap: raise RuntimeError('SPEND_CAP')
        r = llm.chat_full(msgs, self.model, self.backend, temperature=0, max_tokens=self.max_tokens, retries=7)
        u = r.get('usage') or {}
        c = u.get('cost') if u.get('cost') is not None else (u.get('prompt_tokens', 0) * self.pin + u.get('completion_tokens', 0) * self.pout)
        msg = r['choices'][0]['message']
        v = dict(content=msg.get('content') or '', usage=dict(prompt=u.get('prompt_tokens'), completion=u.get('completion_tokens'), cost=c), provider=r.get('provider'), model=r.get('model'))
        with self.lock: self.cost += float(c or 0); self.calls += 1
        self.cache.put(k, v)  # cache every answer (parsing happens at read time), so reruns never re-spend
        return v
def build_jobs(items, phases):
    ps, pu = template('pairwise_prompt.md'); ss, su = template('single_prompt.md'); jobs = []
    for it in items:
        ph = 'calibrate' if it['kind'] == 'easy' else 'nearmiss'
        if ph in phases:
            for order in ('orig', 'swapped'):
                d = it if order == 'orig' else dict(it, A=it['B'], B=it['A'], expected_winner='B' if it['expected_winner'] == 'A' else 'A')
                jobs.append(dict(phase=ph, id=it['id'], order=order, kind=it['kind'], rule_id=it['rule_id'], expected=d['expected_winner'], sys=ps, user=fill(pu, d)))
        if 'single' in phases:
            for side in 'AB':
                good = side == it['expected_winner']
                jobs.append(dict(phase='single', id=it['id'], order=side, kind=it['kind'], rule_id=it['rule_id'], side_is=('compliant' if good else 'violating'),
                                 expected='pass' if good else 'fail', sys=ss, user=fill(su, dict(it, text=it[side]))))
    return jobs
def run(judge, jobs, workers):
    def one(j):
        try: v = judge.ask(j['sys'], j['user'])
        except Exception as e:
            judge.errors[type(e).__name__] += 1
            return dict({k: j[k] for k in j if k not in ('sys', 'user')}, error=f'{type(e).__name__}: {str(e)[:150]}')
        o = parse(v['content'])
        return dict({k: j[k] for k in j if k not in ('sys', 'user')}, out=o, raw=None if o else v['content'][:500], cost=v['usage'].get('cost'))
    with cf.ThreadPoolExecutor(workers) as ex: return list(ex.map(one, jobs))
def probe(backend, model, workers=3):
    """5 real pairwise prompts; usable if >=4 return parseable JSON without exhausting retries."""
    items = [json.loads(l) for l in open(f'{B}/evals/pairwise.jsonl')][:5]
    j = Judge(backend, model, (0, 0), 1e9); j.cache = llm.Cache(f'{OUT}/probe_cache.jsonl')
    t = time.time(); res = run(j, build_jobs(items, {'calibrate', 'nearmiss'})[::2], workers)
    ok = sum(1 for r in res if r.get('out') and r['out'].get('winner') in ('A', 'B'))
    return ok, len(res), round(time.time() - t, 1), dict(j.errors)
def pick_model(backend, force=None, log=None, paid_only=False):
    ms = models()
    if force: return force, ms.get(force)
    for mid in ([] if paid_only else FREE_PREF) + ([] if paid_only else sorted(m for m in ms if m.endswith(':free') and m not in FREE_PREF)):
        if mid not in ms or re.search(r'safety|code|lfm|nano|xs-', mid): continue
        ok, n, secs, errs = probe(backend, mid); log.append(dict(model=mid, probe_ok=ok, probe_n=n, seconds=secs, errors=errs))
        if ok >= n - 1: return mid, ms[mid]
    for mid in PAID_PREF:
        if mid in ms and price(ms[mid])[0] * 1e6 < 1.0:
            ok, n, secs, errs = probe(backend, mid); log.append(dict(model=mid, probe_ok=ok, probe_n=n, seconds=secs, errors=errs))
            if ok >= n - 1: return mid, ms[mid]
    return None, None
def summarize(res, rules):
    S = {}
    def acc(rs, key='winner'):
        rs = [r for r in rs if r.get('out') and r['out'].get(key) is not None]
        return dict(n=len(rs), correct=sum(r['out'][key] == r['expected'] for r in rs))
    for ph in ('calibrate', 'nearmiss'):
        rs = [r for r in res if r['phase'] == ph]; ok = [r for r in rs if r.get('out')]
        s = dict(overall=acc(rs), errors=len(rs) - len(ok),
                 when_correct_is_A=acc([r for r in rs if r['expected'] == 'A']), when_correct_is_B=acc([r for r in rs if r['expected'] == 'B']),
                 chose_A=sum(1 for r in ok if r['out'].get('winner') == 'A'), n_answered=len(ok))
        byid = collections.defaultdict(dict)
        for r in ok: byid[r['id']][r['order']] = r['out'].get('winner') == r['expected']
        both = [v for v in byid.values() if len(v) == 2]
        s['pairs_both_orders'] = dict(n=len(both), both_correct=sum(all(v.values()) for v in both), order_flip=sum(v['orig'] != v['swapped'] for v in both))
        s['by_family'] = {f: acc([r for r in rs if r['rule_id'][0] == f]) for f in 'ABCDE' if any(r['rule_id'][0] == f for r in rs)}
        s['by_check_type'] = {ct: acc([r for r in rs if rules[r['rule_id']]['check_type'] == ct]) for ct in ('deterministic', 'judgment')}
        # approvable-as-is flags in pairwise output: violating side should be False; near-miss compliant side should be True
        fl = collections.Counter()
        for r in ok:
            o = r['out']; good, bad = r['expected'], ('B' if r['expected'] == 'A' else 'A')
            fl['violating_flagged_not_approvable'] += o.get(f'{bad}_approvable') is False; fl['violating_n'] += 1
            fl['compliant_marked_approvable'] += o.get(f'{good}_approvable') is True; fl['compliant_n'] += 1
        s['approvable_flags'] = dict(fl); S[ph] = s
    rs = [r for r in res if r['phase'] == 'single']
    S['single'] = {f'{k}_{side}': acc([r for r in rs if r['kind'] == k and r['side_is'] == side], 'verdict') for k in ('easy', 'near_miss') for side in ('violating', 'compliant')}
    S['single']['errors'] = sum(1 for r in rs if not r.get('out'))
    S['single']['missing_context_flagged'] = sum(1 for r in rs if r.get('out') and r['out'].get('missing_context'))
    return S
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--backend', default='openrouter'); ap.add_argument('--model'); ap.add_argument('--cap', type=float, default=3.0)
    ap.add_argument('--phases', default='calibrate,nearmiss,single'); ap.add_argument('--limit', type=int); ap.add_argument('--workers', type=int)
    ap.add_argument('--paid', action='store_true', help='skip free models (use after free tier rate-limits)'); ap.add_argument('--note', default=''); a = ap.parse_args()
    st = dict(backend=a.backend, at=now(), ran=False)
    def done(**kw):
        st.update(kw); json.dump(st, open(f'{OUT}/status.json', 'w'), indent=1); print(json.dumps({k: v for k, v in st.items() if k not in ('summary',)})[:1500]); return st
    if not llm.available(a.backend): return done(reason=f'no API key for {a.backend}')
    log = []; mid, meta = (a.model, models().get(a.model)) if a.model else pick_model(a.backend, log=log, paid_only=a.paid)
    st['model_selection_log'] = log; st['note'] = a.note
    if not mid: return done(reason='no free or cheap model passed the probe')
    pin, pout = price(meta) if meta else (0, 0)
    st.update(model=mid, pricing_per_million=dict(input=round(pin * 1e6, 4), output=round(pout * 1e6, 4)), free=mid.endswith(':free'))
    items = [json.loads(l) for l in open(f'{B}/evals/pairwise.jsonl')][:a.limit]
    rules = {r['id']: r for f in sorted(glob.glob(f'{B}/rules/[a-e]_*.json')) for r in json.load(open(f))['rules']}
    phases = set(a.phases.split(','))
    jobs = build_jobs(items, phases); judge = Judge(a.backend, mid, (pin, pout), a.cap)
    unc = [j for j in jobs if judge.cache.get(llm.Cache.key(mid, [{'role': 'system', 'content': j['sys']}, {'role': 'user', 'content': j['user']}], t=0, mt=judge.max_tokens)) is None]
    proj = sum(len(j['sys']) + len(j['user']) for j in unc) / 3.5 * pin + len(unc) * 1200 * pout  # 1200 output tokens/call incl. reasoning (conservative)
    st['projected_cost_usd'] = round(proj, 4); st['jobs'] = len(jobs); st['uncached_jobs'] = len(unc)
    if proj > a.cap: return done(reason=f'projected cost ${proj:.2f} exceeds cap ${a.cap}')
    workers = a.workers or (3 if st['free'] else 8)
    res = []
    for ph in ('calibrate', 'nearmiss', 'single'):  # calibration first, per method.md
        js = [j for j in jobs if j['phase'] == ph]
        if not js: continue
        t = time.time(); r = run(judge, js, workers); res += r
        err = sum(1 for x in r if 'error' in x)
        print(f'{ph}: {len(js)} jobs, {err} errors, {time.time()-t:.0f}s, cost so far ${judge.cost:.4f}', flush=True)
        if any('SPEND_CAP' in x.get('error', '') for x in r): st['stopped'] = f'spend cap ${a.cap} reached during {ph}'; break
        if err > 0.1 * len(js): st['stopped'] = f'{err}/{len(js)} errors in {ph} (rate limits or unreliable model)'; break
    with open(f'{OUT}/raw.jsonl', 'w') as f:
        for x in res: f.write(json.dumps(dict(x, model=mid), ensure_ascii=False) + '\n')
    tot = collections.Counter()
    for fn in ('cache.jsonl', 'probe_cache.jsonl'):
        if os.path.exists(f'{OUT}/{fn}'):
            for l in open(f'{OUT}/{fn}'):
                v = json.loads(l)['v']; tot[v.get('model') or '?'] += float((v.get('usage') or {}).get('cost') or 0)
    return done(ran=True, at=now(), cumulative_cost_usd_by_model={k: round(v, 4) for k, v in tot.items()}, cumulative_cost_usd=round(sum(tot.values()), 4), cost_usd_this_run=round(judge.cost, 4), api_calls_this_run=judge.calls, cache_hits=judge.cached,
                errors=dict(judge.errors), summary=summarize(res, rules))
if __name__ == '__main__': main()
