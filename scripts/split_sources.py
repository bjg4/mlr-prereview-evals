# Split an Exa multi-URL fetch dump into rules/sources/<slug>.txt (decodes base64 PDFs via pdftotext)
import sys,re,base64,subprocess,os
D=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'rules','sources')
txt=open(sys.argv[1],encoding='utf-8',errors='replace').read()
parts=re.split(r'^URL: (\S+)\s*$',txt,flags=re.M)
for i in range(1,len(parts),2):
    url,body=parts[i],parts[i+1]
    body=re.sub(r'\n# [^\n]*\s*$','',body.strip())
    slug=re.sub(r'[^A-Za-z0-9]+','_',re.sub(r'^https?://(www\.)?','',url))[:90].strip('_')
    out=f'{D}/{slug}.txt'; b=re.sub(r'\s+','',body); kind='text'
    if b.startswith('JVBER'):
        pdf=base64.b64decode(b+'='*(-len(b)%4)); p=f'{D}/pdf/{slug}.pdf'; open(p,'wb').write(pdf)
        r=subprocess.run(['pdftotext','-layout',p,out],capture_output=True); kind='pdf' if r.returncode==0 and os.path.getsize(out)>500 else 'pdf-fail'
    else: open(out,'w').write(f'SOURCE_URL: {url}\n\n'+body)
    print(slug,kind,os.path.getsize(out) if os.path.exists(out) else 0)
