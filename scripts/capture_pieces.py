"""Capture DTC + HCP homepages as MLR test pieces. Read-only: never clicks gates, submits forms, or accepts cookies.
Overlays (cookie banner, HCP attestation modal) are hidden with CSS for the 'clean' screenshot; the as-landed screenshot keeps them."""
import asyncio, json, os, re, subprocess, datetime, sys
from playwright.async_api import async_playwright
BASE=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"pieces")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
MUA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
PIECES=[
 dict(slug="keytruda_consumer",url="https://www.keytruda.com/",audience="consumer",drug="keytruda"),
 dict(slug="keytruda_hcp",url="https://www.keytrudahcp.com/",audience="hcp",drug="keytruda"),
 dict(slug="eliquis_consumer",url="https://www.eliquis.com/",audience="consumer",drug="eliquis"),
 dict(slug="eliquis_hcp",url="https://www.eliquis.com/eliquis/hcp",audience="hcp",drug="eliquis"),
 dict(slug="mounjaro_consumer",url="https://mounjaro.lilly.com/",audience="consumer",drug="mounjaro"),
 dict(slug="mounjaro_hcp",url="https://mounjaro.lilly.com/hcp",audience="hcp",drug="mounjaro"),
]
if len(sys.argv)>1: PIECES=[p for p in PIECES if p["slug"] in sys.argv[1:]]
HIDE_CSS="""
#onetrust-consent-sdk,#onetrust-banner-sdk,.onetrust-pc-dark-filter,#hcpVerifyEl,.modal-backdrop,
[class*=HCPAcknowledgement__Modal]{display:none!important}
html,body{overflow-y:auto!important;height:auto!important}
"""
# DOM -> markdown-ish text: headings, list items, paragraphs, in document order, skipping display:none/script/style.
TEXT_JS=r"""(arg) => {
 arg=arg||{}; const roots=arg.sel?[...document.querySelectorAll(arg.sel)]:[document.body];
 const BLOCK=new Set(['P','DIV','SECTION','ARTICLE','HEADER','FOOTER','NAV','ASIDE','MAIN','LI','UL','OL','TABLE','TR','TD','TH','H1','H2','H3','H4','H5','H6','BR','FIGURE','FIGCAPTION','BLOCKQUOTE','DL','DT','DD','FORM','BUTTON','LABEL']);
 const SKIP=new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','SVG','IFRAME','META','LINK']);
 let out=[]; let line='';
 const flush=()=>{const t=line.replace(/[ \t\u00a0]+/g,' ').trim(); if(t) out.push(t); line='';};
 function walk(n, hidden){
  if(n.nodeType===3){ if(!hidden) line+=n.nodeValue; return; }
  if(n.nodeType!==1) return;
  if(SKIP.has(n.tagName)) return;
  const cs=getComputedStyle(n);
  if(cs.display==='none' && !arg.includeHidden) return;
  const vis = cs.visibility==='hidden';
  const tag=n.tagName; const blk=BLOCK.has(tag)||cs.display==='block'||cs.display==='flex'||cs.display==='grid'||cs.display==='list-item'||cs.display==='table-row';
  if(blk) flush();
  if(/^H[1-6]$/.test(tag)) line+='#'.repeat(+tag[1])+' ';
  if(tag==='LI') line+='- ';
  if(tag==='IMG'){const a=(n.getAttribute('alt')||'').trim(); if(a) line+='[img: '+a+'] ';}
  if(tag==='SUP') line+='^';
  for(const c of n.childNodes) walk(c, hidden||vis);
  if(blk) flush();
 }
 for(const r of roots){ walk(r,false); flush(); }
 // collapse consecutive duplicates
 const res=[]; for(const l of out){ if(res[res.length-1]!==l) res.push(l); }
 return res.join('\n');
}"""
ISI_JS=r"""() => {
 // candidate ISI containers: id/class mentions isi or safety, and text mentions safety information
 const c=[...document.querySelectorAll('[id*=isi i],[class*=isi i],[id*=safety i],[class*=safety i]')]
   .filter(e=>/safety information|WARNING/i.test(e.textContent||'') && (e.textContent||'').length < 0.8*document.body.textContent.length && getComputedStyle(e).display!=='none');
 return c.map(e=>{const r=e.getBoundingClientRect(); const s=getComputedStyle(e);
   return {tag:e.tagName,id:e.id,cls:(e.className||'').toString().slice(0,100),position:s.position,display:s.display,
     height:Math.round(r.height),textLen:(e.textContent||'').replace(/\s+/g,' ').length,
     text:'', el:e}}).sort((a,b)=>b.textLen-a.textLen || (a.position==='fixed')-(b.position==='fixed')).slice(0,12)
   .map((c,i)=>{ if(i===0) c.el.setAttribute('data-mlr-isi','1'); delete c.el; return c; });
}"""
GATE_JS=r"""() => {
 const hits=[];
 document.querySelectorAll('body *').forEach(e=>{
  const s=getComputedStyle(e); if(!(s.position==='fixed'||s.position==='absolute')) return;
  const r=e.getBoundingClientRect(); if(r.width<200||r.height<100||s.display==='none'||s.visibility==='hidden'||+s.opacity===0) return;
  const t=(e.innerText||'').trim();
  if(/health ?care professional/i.test(t) && t.length<800 && /(continue|proceed|I am)/i.test(t)) hits.push({id:e.id,cls:(e.className||'').toString().slice(0,80),text:t});
 });
 // keep smallest-text unique
 const seen=new Set(); return hits.filter(h=>{if(seen.has(h.text))return false; seen.add(h.text); return true}).slice(0,3);
}"""
async def autoscroll(pg):
    await pg.evaluate("""async()=>{const H=()=>document.documentElement.scrollHeight;let y=0;
      while(y<H() && y<60000){window.scrollTo(0,y);y+=600;await new Promise(r=>setTimeout(r,250));}
      window.scrollTo(0,0);}""")
    await pg.wait_for_timeout(1500)
def now_pt(): return datetime.datetime.now().astimezone().isoformat(timespec="seconds")
async def capture(b, p):
    d=f"{BASE}/{p['slug']}"; os.makedirs(d,exist_ok=True); meta={"slug":p["slug"],"requested_url":p["url"],"audience":p["audience"],"artifacts":{},"notes":[]}
    meta["capture_started_pt"]=now_pt()
    # 1) raw HTML via curl
    r=subprocess.run(["curl","-sSL","--compressed","-A",UA,"-H","Accept-Language: en-US,en;q=0.9","--max-time","40","-o",f"{d}/page.html","-w","%{http_code} %{url_effective}",p["url"]],capture_output=True,text=True)
    code,_,eff=r.stdout.partition(" ")
    meta["raw_html"]={"http_status":code,"final_url":eff,"bytes":os.path.getsize(f"{d}/page.html") if os.path.exists(f"{d}/page.html") else 0}
    meta["artifacts"]["page.html"]="ok" if code=="200" and meta["raw_html"]["bytes"]>1000 else f"fail ({code})"
    # 2) desktop render
    ctx=await b.new_context(viewport={"width":1440,"height":900},user_agent=UA,locale="en-US",timezone_id="America/Los_Angeles")
    pg=await ctx.new_page()
    resp=await pg.goto(p["url"],wait_until="domcontentloaded",timeout=90000)
    try: await pg.wait_for_load_state("networkidle",timeout=20000)
    except Exception: meta["notes"].append("networkidle not reached in 20s; captured after timeout")
    await pg.wait_for_timeout(4000)
    meta["final_url"]=pg.url; meta["page_title"]=await pg.title(); meta["render_http_status"]=resp.status if resp else None
    gate=await pg.evaluate(GATE_JS)
    cookie=await pg.evaluate("()=>{const e=document.querySelector('#onetrust-banner-sdk');if(!e)return null;const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'?e.innerText.slice(0,400):null}")
    meta["hcp_attestation_gate"]={"appeared":bool(gate),"gate_text":gate[0]["text"] if gate else None,
       "handling":"Not clicked. Gate hidden with CSS for clean screenshot/text; as-landed screenshot keeps it. Content behind gate is already in the DOM at the direct URL." if gate else None}
    meta["cookie_banner"]={"appeared":bool(cookie),"text":cookie,"handling":"Not accepted/rejected; hidden with CSS for clean screenshot" if cookie else None}
    await pg.screenshot(path=f"{d}/screenshot_as_landed.png")  # viewport, overlays intact
    meta["artifacts"]["screenshot_as_landed.png"]="ok"
    await autoscroll(pg)
    await pg.add_style_tag(content=HIDE_CSS); await pg.wait_for_timeout(800)
    txt=await pg.evaluate(TEXT_JS)
    open(f"{d}/page.txt","w").write(f"SOURCE: {pg.url}\nCAPTURED: {meta['capture_started_pt']}\nAUDIENCE: {p['audience']}\n(Text extracted from rendered DOM in document order; '#' = heading level, '- ' = list item, '^' = superscript, [img: alt] = image alt text. Elements with display:none excluded; collapsed/sticky ISI trays included.)\n\n"+txt+"\n")
    meta["artifacts"]["page.txt"]="ok" if len(txt)>2000 else f"suspect (len {len(txt)})"
    isi=await pg.evaluate(ISI_JS)
    meta["isi_containers"]=[{k:v for k,v in c.items() if k!="text"} for c in isi]
    if isi:
        isi_txt=await pg.evaluate(TEXT_JS,{"sel":"[data-mlr-isi]","includeHidden":True})
        open(f"{d}/isi.txt","w").write(isi_txt+"\n"); meta["artifacts"]["isi.txt"]="ok" if len(isi_txt)>1500 else f"suspect (len {len(isi_txt)})"
        meta["isi_has_sticky_tray"]=any(c["position"] in("fixed","sticky") for c in isi)
        meta["isi_chars_full"]=len(isi_txt)
    else:
        isi_txt=""; meta["artifacts"]["isi.txt"]="not found by selector (check page.txt)"
    footer_txt=await pg.evaluate(TEXT_JS,{"sel":"footer","includeHidden":True})
    with open(f"{d}/page.txt","a") as f:
        f.write("\n\n======== APPENDIX A: FULL ISI CONTAINER TEXT (from DOM, includes content hidden in a collapsed/sticky tray; duplicates the visible ISI above where it was already shown) ========\n\n"+(isi_txt or "[no ISI container found]")+"\n")
        f.write("\n======== APPENDIX B: <footer> TEXT (from DOM, incl. hidden) ========\n\n"+(footer_txt or "[no <footer> element]")+"\n")
    lowered=(txt+isi_txt).lower()
    meta["isi_check"]={"page_txt_contains_'important/selected safety information'":("important safety information" in lowered or "selected safety information" in lowered),
                       "page_txt_contains_'warning'":"warning" in lowered}
    html=await pg.content(); open(f"{d}/page.rendered.html","w").write(html); meta["artifacts"]["page.rendered.html"]="ok"
    links=await pg.evaluate("()=>[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>/\\.pdf|uspi|medguide|prescrib/i.test(h)))]")
    meta["pi_and_label_links_on_page"]=links
    await pg.screenshot(path=f"{d}/screenshot.png",full_page=True)
    meta["artifacts"]["screenshot.png"]="ok"
    meta["page_height_px"]=await pg.evaluate("document.documentElement.scrollHeight")
    try:
        url0=pg.url
        btn=await pg.query_selector("[data-mlr-isi] [role=button][aria-expanded=false], [data-mlr-isi] button[aria-expanded=false]")
        if not btn:
            loc=pg.get_by_text(re.compile(r"^\s*more important safety information\s*$",re.I))
            if await loc.count(): btn=await loc.first.element_handle()
        if btn and await btn.is_visible():
            await btn.click(timeout=5000); await pg.wait_for_timeout(1500)
            if pg.url==url0:
                await pg.screenshot(path=f"{d}/screenshot_isi_expanded.png",full_page=True); meta["artifacts"]["screenshot_isi_expanded.png"]="ok (clicked ISI tray expand toggle; full-page shot)"
        else: meta["artifacts"]["screenshot_isi_expanded.png"]="n/a (no collapsed ISI toggle found)"
    except Exception as e: meta["artifacts"]["screenshot_isi_expanded.png"]=f"fail: {e}"[:200]
    await ctx.close()
    # 3) mobile
    try:
        mctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True,user_agent=MUA,locale="en-US",timezone_id="America/Los_Angeles")
        mp=await mctx.new_page(); await mp.goto(p["url"],wait_until="domcontentloaded",timeout=90000)
        try: await mp.wait_for_load_state("networkidle",timeout=20000)
        except Exception: pass
        await mp.wait_for_timeout(3000); await mp.screenshot(path=f"{d}/screenshot_mobile_as_landed.png")
        await autoscroll(mp); await mp.add_style_tag(content=HIDE_CSS); await mp.wait_for_timeout(800)
        try:
            await mp.screenshot(path=f"{d}/screenshot_mobile.png",full_page=True); meta["artifacts"]["screenshot_mobile.png"]="ok"
        except Exception:
            await mctx.close()
            mctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=1,is_mobile=True,has_touch=True,user_agent=MUA,locale="en-US",timezone_id="America/Los_Angeles")
            mp=await mctx.new_page(); await mp.goto(p["url"],wait_until="domcontentloaded",timeout=90000); await mp.wait_for_timeout(6000)
            await autoscroll(mp); await mp.add_style_tag(content=HIDE_CSS); await mp.wait_for_timeout(800)
            await mp.screenshot(path=f"{d}/screenshot_mobile.png",full_page=True); meta["artifacts"]["screenshot_mobile.png"]="ok (1x scale retry)"
        await mctx.close()
    except Exception as e: meta["artifacts"]["screenshot_mobile.png"]=f"fail: {e}"
    meta["capture_finished_pt"]=now_pt()
    return meta
async def main():
    async with async_playwright() as pw:
        b=await pw.chromium.launch(channel="chrome",headless=True)
        for p in PIECES:
            try: m=await capture(b,p)
            except Exception as e: m={"slug":p["slug"],"error":repr(e)}
            os.makedirs(f"{BASE}/{p['slug']}",exist_ok=True)
            prev=f"{BASE}/{p['slug']}/meta.json"
            json.dump(m,open(f"{BASE}/{p['slug']}/_capture.json","w"),indent=2)
            print(p["slug"], json.dumps({k:m.get(k) for k in ("final_url","artifacts","hcp_attestation_gate","isi_check","error")})[:900])
        await b.close()
asyncio.run(main())
