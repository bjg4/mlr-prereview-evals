import json, glob, os, csv, collections, datetime
B=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); S=f'{B}/scripts'
CANON=[("Omission of risk","Omission of risk information"),
("Minimization of risk","Minimization of risk"),
("Lack of fair balance","Lack of fair balance / risk prominence"),
("Distracting visuals","Distracting presentation during risk/major statement (TV)"),
("Major statement not in dual","Major statement not in dual modality (TV)"),
("Adequate provision","Missing adequate provision / brief summary"),
("Overstatement of efficacy","Overstatement of efficacy"),
("Misleading presentation of study data","Misleading presentation of study data (post hoc / exploratory / single-arm)"),
("Unsupported PRO","Unsupported PRO / quality-of-life claims"),
("Unsubstantiated superiority","Unsubstantiated superiority / comparative claims"),
("Unsubstantiated efficacy","Unsubstantiated efficacy / mechanism claims"),
("Unsubstantiated claim","Unsubstantiated efficacy / mechanism claims"),
("Broadening of indication","Broadening of indication / omission of material indication facts"),
("Omission of material facts about indication","Broadening of indication / omission of material indication facts"),
("Misleading claims about safety","Misleading claims about safety"),
("Preapproval promotion","Promotion of investigational / unapproved drug or use"),
("Unapproved","Promotion of investigational / unapproved drug or use"),
("Missing investigational","Promotion of investigational / unapproved drug or use"),
("Failure to submit","Failure to submit at first use (Form FDA 2253)"),
("Established name","Failure to use established name / required labeling elements"),
("Misleading sameness","Misleading claims re compounded drug sameness"),
("Misleading representation of drug","Misleading representation of drug identity/source"),
("Misleading storage","Misleading administration / storage / handling presentation"),
("Distracting presentation of material efficacy qualifier","Distracting presentation during risk/major statement (TV)"),
("Minimization of disease seriousness","Broadening of indication / omission of material indication facts"),
("Misleading citation of treatment guidelines","Misleading citation of treatment guidelines / references"),
("Distracting presentation during risk","Distracting presentation during risk/major statement (TV)"),
("Misleading administration","Misleading administration / storage / handling presentation"),
("Failure to use established name","Failure to use established name / required labeling elements"),
("Promotion of investigational","Promotion of investigational / unapproved drug or use"),
("Other","Other")]
def AUD(a):
    a=a.upper(); d='DTC' in a; h='HCP' in a
    return 'DTC+HCP' if d and h else ('DTC' if d else ('HCP' if h else a))
def canon(c):
    for p,n in CANON:
        if c.startswith(p): return n
    return "UNMAPPED:"+c
rows=[l.rstrip('\n').split('\t') for l in open(f'{S}/index_rows.tsv') if l.strip()]
wl=[l.rstrip('\n').split('\t') for l in open(f'{S}/wl_rows.tsv') if l.strip()] if os.path.exists(f'{S}/wl_rows.tsv') else []
man=[]
for r in rows:
    d,co,pr,mid,promo=(r+['']*5)[:5]
    lid=f"UL-{d.replace('-','')}-{mid}"
    man.append(dict(letter_id=lid,letter_date=d,company=co,product=pr,letter_type="Untitled Letter",url=f"https://www.fda.gov/media/{mid}/download",promo_material_urls=";".join(f"https://www.fda.gov/media/{m}/download" for m in promo.split(',') if m)))
for r in wl:
    d,co,pr,url,slug=(r+['']*5)[:5]
    man.append(dict(letter_id=f"WL-{d.replace('-','')}-{slug}",letter_date=d,company=co,product=pr,letter_type="Warning Letter",url=url,promo_material_urls=""))
cases=[]; out_man=[]
for m in man:
    f=f"{S}/cases/{m['letter_id']}.json"
    if os.path.exists(f):
        j=json.load(open(f))
        m.update(piece_type=j.get('piece_type',''),audience=AUD(j.get('audience','')),regulations_cited_in_letter=j.get('regs_in_letter',''),status=j.get('status','processed'),status_note=j.get('note',''),n_cases=len(j.get('cases',[])))
        if j.get('company'): m['company']=j['company']
        for i,c in enumerate(j.get('cases',[]),1):
            cases.append(dict(id=f"{m['letter_id']}-v{i}",source_letter=m['letter_id'],letter_type=m['letter_type'],letter_date=m['letter_date'],company=m['company'],product=m['product'],piece_type=m['piece_type'],audience=AUD(m['audience']),category=canon(c['cat']),letter_category_label=c['cat'],letter_heading=c.get('heading',''),claim_text=c['claim'],context=c.get('context',''),expected_flag=True,fda_rationale=c['rationale'],regulation=c['reg'],check_type=c['ct'],suggested_check=c['check'],source_url=m['url']))
    else:
        m.update(piece_type='',audience='',regulations_cited_in_letter='',status='not_processed',status_note='Not yet read (time/context budget); queued for next pass',n_cases=0)
    out_man.append(m)
os.makedirs(f'{B}/evals',exist_ok=True)
with open(f'{B}/evals/opdp_cases.jsonl','w') as fo:
    for c in cases: fo.write(json.dumps(c,ensure_ascii=False)+'\n')
cols=['letter_id','letter_date','letter_type','company','product','piece_type','audience','url','promo_material_urls','regulations_cited_in_letter','status','status_note','n_cases']
with open(f'{B}/letters/manifest.csv','w',newline='') as fo:
    w=csv.DictWriter(fo,fieldnames=cols,extrasaction='ignore'); w.writeheader(); [w.writerow(m) for m in out_man]
json.dump(out_man,open(f'{B}/letters/manifest.json','w'),indent=1,ensure_ascii=False)
# taxonomy
cc=collections.Counter(c['category'] for c in cases)
ct=collections.defaultdict(collections.Counter)
for c in cases: ct[c['category']][c['check_type']]+=1
lettersper=collections.defaultdict(set)
for c in cases: lettersper[c['category']].add(c['source_letter'])
st=collections.Counter(m['status'] for m in out_man)
proc=[m for m in out_man if m['status']=='processed']
yrs=sorted({m['letter_date'][:4] for m in proc})
tot=collections.Counter(c['check_type'] for c in cases)
L=["# OPDP violation taxonomy (auto-generated by scripts/build.py)","",f"Generated {datetime.date.today()}. Letters processed: {len(proc)} ({', '.join(yrs)}); not processed: {st.get('not_processed',0)}; skipped: {st.get('skipped',0)}. Cases: {len(cases)} (deterministic {tot['deterministic']}, judgment {tot['judgment']}).","",
"Category = normalized bucket; each case also keeps `letter_category_label` (finer label, using the letter's own heading when it has one).","",
"| Category | Cases | Letters | Deterministic | Judgment | Primary check type |","|---|---|---|---|---|---|"]
for k,v in cc.most_common():
    d=ct[k]['deterministic']; j=ct[k]['judgment']
    L.append(f"| {k} | {v} | {len(lettersper[k])} | {d} | {j} | {'deterministic' if d>j else ('judgment' if j>d else 'mixed')} |")
L+=["","## Category definitions and how to check them",""]
open(f'{B}/evals/taxonomy_table.md','w').write("\n".join(L)+"\n")
print(len(proc),'processed;',st, len(cases),'cases;',dict(tot))
for k,v in cc.most_common(): print(v,k,dict(ct[k]))

import subprocess,sys
subprocess.run([sys.executable,f"{B}/scripts/verify.py"],check=True)
# ---- phase 2: rulebook, deterministic evals, controls, pairwise, report ----
# make_controls.py reuses cached LLM drafts (evals/controls_raw.jsonl) and agent-authored rewrites (evals/controls_manual.py);
# it only calls the API for selected cases covered by neither. The judge runs only if MARGIN_RUN_JUDGE=1 (it costs API credits).
# split.py is a no-op once evals/splits.json exists (the split is frozen); write_split_files.py materializes evals/dev and evals/holdout.
for step in ["scripts/build_rules.py","evals/make_controls.py","evals/run_deterministic.py","evals/split.py","evals/make_pairwise.py","evals/write_split_files.py"]:
    subprocess.run([sys.executable,f"{B}/{step}"],check=True)
if os.environ.get("MARGIN_RUN_JUDGE")=="1":
    # pin the model of the last completed run so a rebuild is served from cache (no re-spend); delete status.json to re-select a model
    _st=f"{B}/judge/results/status.json"; _m=json.load(open(_st)).get("model") if os.path.exists(_st) else None
    _note=json.load(open(_st)).get("note","") if os.path.exists(_st) else ""
    subprocess.run([sys.executable,f"{B}/judge/run_judge.py"]+(["--model",_m,"--note",_note] if _m else []),check=True)
# Self-improvement loop (costs API credits): MARGIN_RUN_LOOP=<round> runs scripts/loop.py --round <round> (score, triage, proposals, evaluate approved).
if os.environ.get("MARGIN_RUN_LOOP"):
    subprocess.run([sys.executable,f"{B}/scripts/loop.py","--round",os.environ["MARGIN_RUN_LOOP"]],check=True)
subprocess.run([sys.executable,f"{B}/evals/make_report.py"],check=True)
