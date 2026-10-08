import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import json,sys
FD="FD&C Act (false or misleading)"
def mk(lid,piece,aud,company,cases,regs="FD&C Act (no CFR section cited in letter text)",note=None):
    d={"id":lid,"piece_type":piece,"audience":aud,"company":company,"regs_in_letter":regs,"status":"processed","cases":[]}
    if note: d["note"]=note
    for c in cases:
        cat,claim,ctx,rat,ct,chk=c[:6]
        d["cases"].append({"cat":cat,"claim":claim,"context":ctx,"rationale":rat,"reg":c[6] if len(c)>6 else FD,"ct":ct,"check":chk})
    json.dump(d,open(f"{_ROOT}/scripts/cases/{lid}.json","w"),ensure_ascii=False,indent=0)
SA="Misleading presentation of study data (single-arm/uncontrolled)"
SA_TTE="Rule: flag PFS/OS/survival/time-to-event claims (incl. cystectomy-free, DSS) when the source trial is single-arm; disclaimers do not count as a fix."
SA_SD="Rule: in single-arm-trial products, flag stable disease / DCR / waterfall plots including SD; disclaimers do not count as a fix."
