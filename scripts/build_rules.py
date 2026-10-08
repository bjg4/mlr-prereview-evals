# Renders rules/<family>.json + rules/index.json from scripts/rules_src.py; links OPDP case ids; verifies quotes against fetched sources.
import json,re,os,sys,collections
sys.path.insert(0,os.path.dirname(__file__)); import rules_src as S
B=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def norm(s): return re.sub(r'[^a-z0-9]+','',s.lower().replace('’',"'").replace('–','-').replace('—','-'))
cases=[json.loads(l) for l in open(f'{B}/evals/opdp_cases.jsonl')]
def linked(link):
    if not link: return []
    out=[]
    for c in cases:
        if 'ids' in link: 
            if c['id'] in link['ids']: out.append(c['id'])
            continue
        if 'cats' in link and c['category'] not in link['cats']: continue
        if 'ct' in link and c['check_type']!=link['ct']: continue
        if 're' in link and not re.search(link['re'],' '.join([c['claim_text'],c['piece_type'],c['suggested_check'],c['fda_rationale']])): continue
        out.append(c['id'])
    return out
srctext={}
def qcheck(r):
    q=r['quote']; src=S.SOURCES[r['source']['key']]
    if not q: return 'no_quote'
    if not src['file']: return 'not_checked (source text not archived; quote taken from FDA search excerpt)'
    if src['file'] not in srctext: srctext[src['file']]=norm(re.sub(r"(?m)^\s*\d{1,4}\s+","",open(f"{B}/rules/sources/{src['file']}",errors="ignore").read()))
    parts=[p for p in re.split(r'\.\.\.|…',q) if len(norm(p))>=10]
    ok=all(norm(p) in srctext[src['file']] for p in parts)
    if not ok and r['source']['key']=='FTC255':  # 255.x quotes live in per-section files
        allt=''.join(norm(open(f"{B}/rules/sources/{f}",errors='ignore').read()) for f in os.listdir(f'{B}/rules/sources') if f.startswith('law_cornell_edu_cfr_text_16_255'))
        ok=all(norm(p) in allt for p in parts)
    return 'verified' if ok else 'NOT_FOUND'
fam=collections.defaultdict(list); idx=[]
for r in S.RULES:
    src=S.SOURCES[r['source']['key']]
    out=dict(id=r['id'],source=dict(document=src['doc'],section=r['source']['section'],url=src['url'],status=src['status'],archived_text=('rules/sources/'+src['file']) if src['file'] else None),
             rule_text=r['rule_text'],verbatim_quote=r['quote'],quote_check=qcheck(r),applies_to=r['applies_to'],check_type=r['check_type'],
             detection=r['detection'],severity=r['severity'],opdp_case_ids=linked(r['link']),note=r['note'])
    fam[r['family']].append(out)
    idx.append(dict(id=r['id'],family=r['family'],check_type=r['check_type'],severity=r['severity'],check_fn=r['detection'].get('check_fn'),n_opdp_cases=len(out['opdp_case_ids']),quote_check=out['quote_check']))
names={'a':'a_statute_regs','b':'b_fda_guidance','c':'c_ftc','d':'d_oig_cia','e':'e_phrma'}
for k,v in fam.items(): json.dump(dict(family=S.FAMILIES[k],rules=v),open(f'{B}/rules/{names[k]}.json','w'),indent=1,ensure_ascii=False)
json.dump(dict(families={names[k]:S.FAMILIES[k] for k in names},sources={k:dict(document=v['doc'],url=v['url'],status=v['status'],archived_text=v['file']) for k,v in S.SOURCES.items()},rules=idx),open(f'{B}/rules/index.json','w'),indent=1,ensure_ascii=False)
c=collections.Counter((i['family'],i['check_type']) for i in idx)
print('rules',len(idx),dict(c)); print('quote checks',collections.Counter(i['quote_check'].split(' (')[0] for i in idx))
print('NOT_FOUND:',[i['id'] for i in idx if i['quote_check']=='NOT_FOUND'])
