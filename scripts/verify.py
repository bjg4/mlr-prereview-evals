# Annotates evals/opdp_cases.jsonl with quote_check and writes letters/text_status.csv
import json,re,os,csv,collections
B=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def norm(s):
    s=s.replace('’',"'").replace('‘',"'").replace('“','"').replace('”','"').replace('–','-').replace('—','-').replace('\u00a0',' ')
    s=re.sub(r'\[\d+(,\d+)*\]','',s)
    return re.sub(r'[^a-z0-9%]+','',s.lower())
wl={l.split('\t')[4].strip():l.split('\t')[3] for l in open(f'{B}/scripts/wl_rows.tsv')}
def tfile(sid):
    if sid.startswith('UL-'): return f"{B}/letters/text/{sid.split('-')[-1]}.txt"
    return f"{B}/letters/text/WL-"+wl[sid.split('-',2)[2]].rstrip('/').split('/')[-1]+'.txt'
status={}
def tstat(sid):
    if sid in status: return status[sid]
    f=tfile(sid)
    if not os.path.exists(f): s='missing'
    else:
        t=open(f,errors='ignore').read()
        if t.lstrip().startswith('%PDF'): s='unusable_raw_pdf'
        elif 'Dear' not in t and 'DEAR' not in t: s='partial'
        elif 'Conclusion and Requested Action' not in t and 'CONCLUSION' not in t: s='partial'
        else: s='full'
    if sid in PARTIAL and s=='full': s='partial'
    status[sid]=s; return s
OVR={'UL-20260624-193472-v1':'verified (manual: letter splits the quote with a footnote)','UL-20201124-144115-v1':'not_found_in_partial_text (manual: archived text lacks page 2; quote taken from full-text WebFetch read)'}
PARTIAL={'UL-20201124-144115'}
rows=[json.loads(l) for l in open(f'{B}/evals/opdp_cases.jsonl')]
cnt=collections.Counter()
for c in rows:
    st=tstat(c['source_letter']); qs=re.findall(r'“([^”]+)”',c['claim_text'])
    frags=[p for q in qs for p in re.split(r'\.\s?\.\s?\.|…|\[[^\]]*\]',q) if len(norm(p))>=12]
    if not frags: r='no_quoted_text (omission/format/visual description)'
    elif st in('missing','unusable_raw_pdf'): r='not_checked (archived text unavailable)'
    else:
        T=norm(open(tfile(c['source_letter']),errors='ignore').read())
        hit=sum(norm(p) in T for p in frags)
        r='verified' if hit==len(frags) else (f'not_found_in_partial_text ({hit}/{len(frags)})' if st=='partial' else f'MISMATCH ({hit}/{len(frags)})')
    r=OVR.get(c['id'],r)
    c['quote_check']=r; cnt[r.split(' (')[0]]+=1
with open(f'{B}/evals/opdp_cases.jsonl','w') as fo:
    for c in rows: fo.write(json.dumps(c,ensure_ascii=False)+'\n')
man=json.load(open(f'{B}/letters/manifest.json'))
with open(f'{B}/letters/text_status.csv','w',newline='') as fo:
    w=csv.writer(fo); w.writerow(['letter_id','status','archived_text_file','archived_text_status'])
    for m in man:
        sid=m['letter_id']; w.writerow([sid,m['status'],os.path.relpath(tfile(sid),B),tstat(sid)])
print(dict(cnt)); print(collections.Counter(status.values()))
print([ (c['id'],c['quote_check']) for c in rows if c['quote_check'].startswith('MISMATCH')])
