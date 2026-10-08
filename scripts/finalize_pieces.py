import json, os, glob, hashlib
BASE=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"pieces")
DRUGS={
 "keytruda":dict(brand="KEYTRUDA", established_name="pembrolizumab", also_promoted="KEYTRUDA QLEX (pembrolizumab and berahyaluronidase alfa-pmph)",
   company="Merck & Co., Inc. (Merck Sharp & Dohme LLC, Rahway, NJ)", therapeutic_area="Oncology (PD-1 inhibitor)", boxed_warning=False,
   fy2025_sales_usd_m=31680,
   pi={"KEYTRUDA_PI":"https://www.merck.com/product/usa/pi_circulars/k/keytruda/keytruda_pi.pdf","KEYTRUDA_QLEX_PI":"https://www.merck.com/product/usa/pi_circulars/k/keytruda_qlex/keytruda_qlex_pi.pdf",
       "KEYTRUDA_Medication_Guide":"https://www.merck.com/product/usa/pi_circulars/k/keytruda/keytruda_mg.pdf","KEYTRUDA_QLEX_Medication_Guide":"https://www.merck.com/product/usa/pi_circulars/k/keytruda_qlex/keytruda_qlex_mg.pdf"},
   pi_local={"KEYTRUDA_PI":"pi/keytruda_pi.pdf (+ .txt), Revised 07/2026","KEYTRUDA_QLEX_PI":"pi/keytruda_qlex_pi.pdf (+ .txt), Revised 08/2026","KEYTRUDA_Medication_Guide":"pi/keytruda_mg.pdf (+ .txt), Revised July 2026"}),
 "eliquis":dict(brand="ELIQUIS", established_name="apixaban", also_promoted=None,
   company="(see manufacturer site)", therapeutic_area="Cardiovascular / anticoagulation (factor Xa inhibitor)", boxed_warning=True,
   fy2025_sales_usd_m=14443,
   pi={"ELIQUIS_PI":"https://packageinserts.bms.com/pi/pi_eliquis.pdf","ELIQUIS_Medication_Guide":"https://packageinserts.bms.com/medguide/medguide_eliquis.pdf"},
   pi_local={"ELIQUIS_PI":"pi/eliquis_pi.pdf (+ .txt), Revised 08/2026","ELIQUIS_Medication_Guide":"pi/eliquis_mg.pdf (+ .txt), Revised 05/2025"}),
 "mounjaro":dict(brand="MOUNJARO", established_name="tirzepatide", also_promoted=None,
   company="Eli Lilly and Company (Lilly USA, LLC)", therapeutic_area="Type 2 diabetes / cardiometabolic (GIP and GLP-1 receptor agonist)", boxed_warning=True,
   fy2025_sales_usd_m=22965,
   pi={"MOUNJARO_PI_PDF":"https://pi.lilly.com/us/mounjaro-uspi.pdf","MOUNJARO_PI_html_linked_from_site":"https://uspl.lilly.com/mounjaro/mounjaro.html?s=pi","MOUNJARO_Medication_Guide_html":"https://uspl.lilly.com/mounjaro/mounjaro.html?s=mg"},
   pi_local={"MOUNJARO_PI_PDF":"pi/mounjaro_pi.pdf (+ .txt), Revised 08/2026; Medication Guide is included in the same PDF"}),
}
TOP_SELLER_SOURCE={"source":"Drug Discovery & Development, 'Pharma 50: The 50 best-selling drugs of FY2025' (built from company filings)","url":"https://www.drugdiscoverytrends.com/pharma-50-the-50-best-selling-drugs-of-fy2025/",
  "year":"FY2025 (calendar 2025) global sales","ranks":{"keytruda":1,"mounjaro":2,"eliquis":6},
  "corroboration":["Wikipedia 'List of largest selling pharmaceutical products' (2025 table: Keytruda $31.6B #1, Mounjaro $23.0B #2, Eliquis $14.7B #6)","Hardman & Co '2025 Pharma Statistics' (Apr 2026): by molecule, Mounjaro+Zepbound $36.5B #1, Keytruda $31.7B"]}
manifest={"created_by":"Margin (MLR pre-review bot) piece capture","capture_script":"scripts/capture_pieces.py","top_seller_basis":TOP_SELLER_SOURCE,
  "method":"raw HTML via curl (Chrome UA); rendered DOM, text and screenshots via headless Google Chrome 154 (Playwright, channel=chrome), desktop 1440px and mobile 390px. No forms submitted, no cookie consent clicked, no HCP attestation clicked: gates/cookie banners hidden with CSS for the clean shots and kept in screenshot_as_landed.png. Only interaction: clicking an ISI tray expand toggle for screenshot_isi_expanded.png where one existed.",
  "pieces":[]}
for d in sorted(glob.glob(f"{BASE}/*_*/_capture.json")):
    c=json.load(open(d)); slug=c["slug"]; drug=slug.split("_")[0]; info=DRUGS[drug]; folder=os.path.dirname(d)
    files={f:os.path.getsize(os.path.join(folder,f)) for f in sorted(os.listdir(folder)) if not f.startswith("_")}
    meta={"slug":slug,"audience":c["audience"],"url_requested":c["requested_url"],"url_final":c.get("final_url"),"page_title":c.get("page_title"),
      "capture_timestamp_pt":c.get("capture_started_pt"),"capture_finished_pt":c.get("capture_finished_pt"),
      "brand":info["brand"],"established_name":info["established_name"],"also_promoted_on_page":info["also_promoted"],"company":info["company"],"therapeutic_area":info["therapeutic_area"],
      "boxed_warning_in_PI":info["boxed_warning"],"official_manufacturer_site":True,
      "hcp_attestation_gate":c.get("hcp_attestation_gate"),"cookie_banner":c.get("cookie_banner"),
      "isi":{"sticky_tray":c.get("isi_has_sticky_tray"),"full_isi_chars":c.get("isi_chars_full"),"containers_detected":c.get("isi_containers"),"checks":c.get("isi_check")},
      "raw_html_fetch":c.get("raw_html"),"render_http_status":c.get("render_http_status"),"page_height_px_desktop":c.get("page_height_px"),
      "artifacts":c.get("artifacts"),"files_bytes":files,
      "prescribing_information":{"urls":info["pi"],"local_copies":info["pi_local"]},
      "label_links_found_on_page":c.get("pi_and_label_links_on_page"),
      "notes":c.get("notes",[])}
    if slug=="eliquis_consumer":
        meta["notes"].append("www.eliquis.com redirects to www.eliquis.bmscustomerconnect.com (BMS-owned domain); this is the official US consumer site. The HCP site lives at www.eliquis.com/eliquis/hcp.")
        meta["notes"].append("Full-page screenshots were cropped to viewport width (1440 desktop / 390 mobile) after capture: an off-screen carousel made Chrome report an ~11,000px-wide canvas.")
    if slug=="eliquis_hcp": meta["notes"].append("Homepage is short (~1,010px); the full ISI lives in a bottom tray. screenshot_isi_expanded.png shows the tray after clicking 'MORE IMPORTANT SAFETY INFORMATION' (a page toggle, not the HCP gate).")
    if slug=="mounjaro_hcp": meta["notes"].append("No click-through attestation modal; page shows an inline banner 'This site is intended for U.S. Healthcare Providers'.")
    if slug in("mounjaro_consumer","mounjaro_hcp"): meta["notes"].append("Full ISI exists only in a sticky bottom tray that is collapsed by default; full text captured from DOM into isi.txt and page.txt Appendix A; screenshot_isi_expanded.png shows the tray opened.")
    json.dump(meta,open(f"{folder}/meta.json","w"),indent=2,ensure_ascii=False)
    manifest["pieces"].append({k:meta[k] for k in ("slug","audience","brand","established_name","company","url_requested","url_final","capture_timestamp_pt")}|{"dir":folder,"hcp_gate":bool((meta["hcp_attestation_gate"] or {}).get("appeared")),"artifacts":meta["artifacts"]})
manifest["prescribing_information"]={k:{"urls":v["pi"],"local":v["pi_local"]} for k,v in DRUGS.items()}
manifest["drugs"]={k:{x:v[x] for x in ("brand","established_name","company","therapeutic_area","fy2025_sales_usd_m","boxed_warning")} for k,v in DRUGS.items()}
json.dump(manifest,open(f"{BASE}/manifest.json","w"),indent=2,ensure_ascii=False)
print(json.dumps([(p["slug"],p["hcp_gate"],p["artifacts"]) for p in manifest["pieces"]],indent=0))
