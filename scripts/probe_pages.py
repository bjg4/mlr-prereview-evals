import asyncio, json, sys
from playwright.async_api import async_playwright
URLS = {
 "keytruda_consumer":"https://www.keytruda.com/",
 "keytruda_hcp":"https://www.keytrudahcp.com/",
 "eliquis_consumer":"https://www.eliquis.com/",
 "eliquis_hcp":"https://www.eliquis.com/eliquis/hcp",
 "mounjaro_consumer":"https://mounjaro.lilly.com/",
 "mounjaro_hcp":"https://mounjaro.lilly.com/hcp",
}
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        for k,u in URLS.items():
            ctx = await b.new_context(viewport={"width":1440,"height":900}, user_agent=UA, locale="en-US", timezone_id="America/Los_Angeles")
            pg = await ctx.new_page()
            try:
                r = await pg.goto(u, wait_until="domcontentloaded", timeout=60000)
                await pg.wait_for_timeout(6000)
                info = await pg.evaluate("""() => {
                  const out=[];
                  document.querySelectorAll('[role=dialog],[aria-modal=true],.modal,[class*=modal],[class*=interstitial],[id*=onetrust-banner],[class*=cookie],[id*=modal]').forEach(e=>{
                    const s=getComputedStyle(e); const r=e.getBoundingClientRect();
                    if(s.display!=='none'&&s.visibility!=='hidden'&&r.width>50&&r.height>50) out.push({tag:e.tagName,id:e.id,cls:(e.className||'').toString().slice(0,80),txt:e.innerText.slice(0,300)});
                  });
                  return {url:location.href,title:document.title,len:document.body.innerText.length,overlays:out.slice(0,8)};
                }""")
                print(k, r.status if r else None, json.dumps(info, indent=1)[:2500])
                await pg.screenshot(path=f"/tmp/probe_{k}.png")
            except Exception as e:
                print(k,"ERR",e)
            await ctx.close()
        await b.close()
asyncio.run(main())
