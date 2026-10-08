import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys,re
for mid in sys.argv[1:]:
    t=open(f'{_ROOT}/letters/text/{mid}.txt').read()
    t=re.sub(r'Reference ID: \d+','',t)
    s=t.find('Dear'); e=t.find('Conclusion and Requested Action')
    if e<0: e=t.find('CONCLUSION')
    b=t[s:e if e>0 else s+12000]
    b=re.sub(r'[ \t]+',' ',b); b=re.sub(r'\n\s*\n+','\n',b)
    b=re.sub(r'\n[^\n]{0,60}\n(?:NDA|BLA|ANDA) \d+[^\n]*\n(?:Page \d+\n)?','\n',b)
    print('=====',mid,len(b)); print(b)
