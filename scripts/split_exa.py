import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys,re,base64,subprocess,os
src=sys.argv[1]
txt=open(src,encoding='utf-8',errors='replace').read()
parts=re.split(r'^URL: (https://www\.fda\.gov/media/(\d+)/download)\s*$',txt,flags=re.M)
for i in range(1,len(parts),3):
    url,mid,body=parts[i],parts[i+1],parts[i+2]
    # strip next "# title" header
    body=re.sub(r'\n# [^\n]*\s*$','',body.strip())
    out=f'{_ROOT}/letters/text/{mid}.txt'
    b=re.sub(r'\s+','',body)
    kind='text'
    if b.startswith('JVBER'):
        try:
            pdf=base64.b64decode(b+'='*(-len(b)%4))
            open(f'{_ROOT}/letters/pdf/{mid}.pdf','wb').write(pdf)
            r=subprocess.run(['pdftotext','-layout',f'{_ROOT}/letters/pdf/{mid}.pdf',out])
            kind='pdf' if r.returncode==0 else 'pdf-fail'
        except Exception as e:
            kind='b64-fail:'+str(e)[:50]
    else:
        open(out,'w').write(body)
    n=os.path.getsize(out) if os.path.exists(out) else 0
    print(mid,kind,n)
