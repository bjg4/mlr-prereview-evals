import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys,re
for mid in sys.argv[1:]:
    t=open(f'{_ROOT}/letters/text/{mid}.txt').read()
    t=re.sub(r'Reference ID: \d+','',t)
    s=t.find('Dear'); e=t.find('Conclusion and Requested Action')
    if e<0: e=t.find('Conclusion')
    b=t[s:e if e>0 else len(t)]
    b=re.sub(r'\s+',' ',b)
    b=re.sub(r'The (?:U\.S\. Food and Drug Administration \(FDA\)|Office of Prescription Drug Promotion \(OPDP\) of the U\.S\. Food and Drug Administration \(FDA\)) has reviewed (?:the|a) ','',b)
    b=re.sub(r'FDA has determined that the [^.]{0,60} (?:is|are) false or misleading\. Thus, [^.]*?\(FD&C Act\)\. ','',b)
    b=re.sub(r'\S+ \S+ Page \d+ [^\n]{0,80}?(?:NDA|BLA) \d+ ?/ ?MA \d+ ','',b)
    print('=====',mid,b[:9000])
