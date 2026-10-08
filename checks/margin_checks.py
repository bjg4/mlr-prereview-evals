"""Margin deterministic checks.

Each check takes a `piece` dict and returns a list of Result dicts:
  {rule_id, check, status: pass|fail|not_applicable|needs_input, evidence: [{start,end,text}], detail}
`run_checks(piece)` runs every deterministic rule in rules/*.json whose check_fn is implemented here.

piece = {
  text: str,                     # all on-page / on-screen / transcript text (required)
  audio_text: str?,              # broadcast audio transcript (optional)
  piece_type: str, audience: str,# e.g. "DTC broadcast TV ad", "DTC" | "HCP" | "payer"
  brand: str?, established_name: str?,
  pi: {indication_qualifiers: [str|[syn..]], limitations_of_use: [...], required_risk_terms: [str|[syn..]],
       indication_terms: [...], trial_design: "single-arm"|...},
  meta: {substantiated_claims: [str], form_2253_id, disseminated, claimed_reminder, investigational, endpoint_status,
         communication_type, endorser_compensated, endorser_verified_user, actor_portrays_hcp, real_hcp_compensated,
         major_statement_audio, major_statement_supers, supers:[{text,seconds}], super_format, audio_wpm, name_sizes,
         program:{...}, approvals:[...], first_use_date, placement:{adult_pct}, age_sensitive, hcei, differs_from_label, unapproved, links:[...]}
}
Statuses: a "fail" on a trigger-type check (e.g. comparative_claim) means "flag for MLR verification", not a final violation.
"""
import re, json, os, glob
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I = re.I

def _spans(rx, text, flags=I, limit=5):
    return [dict(start=m.start(), end=m.end(), text=text[max(0, m.start()-40):m.end()+40].strip()) for m in list(re.finditer(rx, text or '', flags))[:limit]]
def _has(rx, text, flags=I): return re.search(rx, text or '', flags) is not None
def _pt(p): return (p.get('piece_type') or '').lower()
def _aud(p): return (p.get('audience') or '').upper()
def _meta(p): return p.get('meta') or {}
def _pi(p): return p.get('pi') or {}
def _substantiated(p, span_text):
    return any(s.lower() in span_text.lower() for s in _meta(p).get('substantiated_claims', []))
def _res(status, evidence=None, detail=''): return dict(status=status, evidence=evidence or [], detail=detail)

BROADCAST = r'tv|television|radio|broadcast|streaming|youtube|video ad|commercial'
CHAR_LIMITED = r'sponsored link|paid search|search(-engine)? ad|search ad|tweet|microblog|banner|sponsored post'
SOCIAL = r'instagram|facebook|tiktok|social|reel|post|x\.com|twitter'
RISK = (r'important safety information|\bISI\b|warning|contraindicat|side effect|adverse (reaction|event)|serious|risk of|may cause|'
        r'allergic|hypersensitivity|do not (take|use)|boxed|stop (taking|using)|tell your (doctor|health ?care provider)|can cause|could cause')
BENEFIT = (r'\btreat|help(s|ed)? |reduc|lower|improv|relief|\bworks?\b|prevent|control|remission|respon|approved (for|in)|indicated|proven|'
           r'lose|clear|heal|surviv|\bPFS\b|\bOS\b|\bDCR\b|efficacy|results|now available|option|deliver|fight|attack|eliminat|protect')

# ---------------------------------------------------------------- name / required elements
def established_name(p):
    b, e, t = p.get('brand'), p.get('established_name'), p.get('text', '')
    if not b or not e: return _res('needs_input', detail='brand and established_name required')
    bm = list(re.finditer(re.escape(b), t, I))
    if not bm: return _res('not_applicable', detail='brand not mentioned')
    ns = _meta(p).get('name_sizes')
    if ns and ns.get('established_px', 0) < 0.5 * ns.get('brand_px', 0):
        return _res('fail', detail=f"established name {ns['established_px']}px < 0.5x brand {ns['brand_px']}px")
    core = re.escape(re.split(r'[\s(,]', e.strip('() '))[0])  # first word of established name
    for m in bm:
        win = re.sub(r'®|™|\(R\)|\bC-?I{1,3}V?\b', '', t[m.end(): m.end() + 80])
        if re.search(core, win[:60], I) and not re.search(r'[.!?]\s', win[:win.lower().find(e.split()[0].lower())] if e.split()[0].lower() in win.lower() else ''):
            return _res('pass', _spans(re.escape(b), t, limit=1))
    return _res('fail', _spans(re.escape(b), t, limit=2), f'"{b}" never followed by established name "{e}" within 60 chars')

def medwatch_statement(p):
    t, pt = p.get('text', ''), _pt(p)
    if 'DTC' not in _aud(p): return _res('not_applicable')
    if re.search(BROADCAST, pt):
        ok = _has(r'medwatch|1.?800.?FDA.?1088|print ad|magazine|\b1.?8\d\d.?\d{3}.?\d{4}', t)
        return _res('pass' if ok else 'fail', detail='TV: needs MedWatch, print-ad reference or toll-free number')
    if not re.search(r'print|magazine|newspaper|published|journal|brochure|ad\b', pt): return _res('not_applicable')
    ok = _has(r'fda\.gov/medwatch', t) and _has(r'1.?800.?FDA.?1088', t)
    return _res('pass' if ok else 'fail', detail='requires fda.gov/medwatch and 1-800-FDA-1088')

def adequate_provision(p):
    t = (p.get('text', '') + ' ' + (p.get('audio_text') or ''))
    if not re.search(BROADCAST, _pt(p)): return _res('not_applicable')
    el = {'phone': r'\b1?.?8\d\d.?\d{3}.?\d{4}\b|1.?8\d\d.?[A-Z]{3,}', 'url': r'\b[\w-]+\.(com|net|org)\b|www\.', 'print': r'print ad|magazine|see (our|the) ad',
          'hcp': r'ask your (doctor|health ?care provider|pharmacist)|talk to your (doctor|health ?care provider)'}
    have = [k for k, rx in el.items() if _has(rx, t)]
    return _res('pass' if len(have) >= 3 else 'fail', detail=f'adequate-provision elements present: {have}')

def reminder_ad(p):
    t, b, m = p.get('text', ''), p.get('brand'), _meta(p)
    if not b or not _has(re.escape(b), t): return _res('not_applicable')
    if not m.get('claimed_reminder') and _has(RISK, t): return _res('not_applicable', detail='has risk content; not relying on reminder exemption')
    ind = _pi(p).get('indication_terms') or [r'migraine|diabetes|cancer|psoriasis|asthma|depress|arthritis|eczema|HIV|obesity|weight|ADHD|schizophren|heart failure|kidney|RSV|lymphoma|anemia']
    ev = [s for rx in ind for s in _spans(rx, t)]
    return _res('fail' if ev else 'pass', ev, 'brand + indication/disease term => not a reminder ad; risk info required')

# ---------------------------------------------------------------- risk presence / coverage / placement
def risk_present(p):
    t, b = p.get('text', '') + ' ' + (p.get('audio_text') or ''), p.get('brand')
    claims = (b and _has(re.escape(b), t) and _has(BENEFIT, t)) or _meta(p).get('makes_claims')
    if not claims: return _res('not_applicable', detail='no brand+benefit claim detected')
    # links/sitelinks to risk content are supplemental, not risk information (SM2014 IV.B points 1 and 3)
    t = re.sub(r'(?i)\b(view|see|click|read|tap)( (the|full|our))? (important safety info\w*|ISI|boxed warning|prescribing information|medication guide|side effects)[^|]*', ' ', t)
    n = len(re.findall(RISK, t, I))
    ok = _has(r'important safety information|\bISI\b', t) and n >= 2 or n >= 2
    return _res('pass' if ok else 'fail', _spans(BENEFIT, t, limit=2), f'risk markers found: {n}')

def _terms_missing(terms, t):
    miss = []
    for term in terms:
        syns = term if isinstance(term, list) else [term]
        if not any(re.search(re.escape(s) if not s.startswith('re:') else s[3:], t, I) for s in syns): miss.append(syns[0])
    return miss

def risk_coverage(p):
    terms = _pi(p).get('required_risk_terms')
    if not terms: return _res('needs_input', detail='pi.required_risk_terms not supplied')
    t = p.get('audio_text') or p.get('text', '')
    miss = _terms_missing(terms, t)
    return _res('fail' if miss else 'pass', detail=f'missing risk items: {miss}' if miss else 'all required risk items present')

def risk_after_close(p):
    segs = _meta(p).get('segments')
    t = ' '.join(segs) if segs else p.get('text', '')
    if not re.search(BROADCAST + '|' + SOCIAL + r'|video|email|podcast', _pt(p)): return _res('not_applicable')
    close = re.search(r'learn more at|visit \S+\.com|brought to you by|see you|sincerely|best regards|thanks for watching|\[end card\]|\[logo\]|\[tag ?line\]', t, I)
    risks = [m.start() for m in re.finditer(RISK, t, I)]
    if not close or not risks: return _res('needs_input' if not close else 'not_applicable', detail='no closing cue or no risk found in ordered text')
    return _res('fail' if min(risks) > close.start() else 'pass', [dict(start=close.start(), end=close.end(), text=t[close.start():close.end()+60])], 'risk first appears after closing cue' if min(risks) > close.start() else '')

# ---------------------------------------------------------------- indication
def indication_qualifiers(p):
    q = list(_pi(p).get('indication_qualifiers') or []) + list(_pi(p).get('limitations_of_use') or [])
    if not q: return _res('needs_input', detail='pi.indication_qualifiers not supplied')
    miss = _terms_missing(q, p.get('text', '') + ' ' + (p.get('audio_text') or ''))
    return _res('fail' if miss else 'pass', detail=f'missing indication qualifiers: {miss}' if miss else 'all qualifiers present')

# ---------------------------------------------------------------- lexical triggers (fail = flag for verification)
NEG = re.compile(r"\b(not|no|never|nor|without|cannot)\b|n't\b|no studies|not been (shown|established)", I)
PLACEBO_CMP = re.compile(r"^\W{0,3}(\[)?[^.|;]{0,40}?\b(placebo|vehicle|baseline|sham|start of (the )?study|alone)\b", I)
def _negated(t, s, window=40):
    pre = t[max(0, s['start'] - window):s['start']]
    pre = re.split(r'[.!?;|]', pre)[-1]  # same sentence only
    return bool(NEG.search(pre))
def _trigger(p, rx, why, negatable=True, placebo_ok=False):
    t = p.get('text', '') + ' ' + (p.get('audio_text') or '')
    ev = [s for s in _spans(rx, t, limit=8) if not _substantiated(p, s['text'])]
    if negatable: ev = [s for s in ev if not _negated(t, s)]
    if placebo_ok: ev = [s for s in ev if not (re.match(r'(?i)\s*(vs\.?|versus|compared (to|with))', t[s['start']:s['end'] + 2]) and PLACEBO_CMP.search(t[s['end']:s['end'] + 60]))]
    return _res('fail' if ev else 'pass', ev, why if ev else '')

COMPARATIVE = r"\bbetter than\b|\bsuperior|more effective|outperform|\bvs\.?\s|\bversus\b|compared (to|with)|\bunlike other|preferred (choice|treatment|option)|\d+(\.\d+)?\s*(x|times)\s+(more|greater|as)|\d+-\d+x more|\d+%\s+more than"
def comparative_claim(p): return _trigger(p, COMPARATIVE, 'comparative claim (non-placebo comparator): needs head-to-head substantial evidence on file', placebo_ok=True)
MINIM = (r"\bsafe(r|st|ly)?\b|well[- ]tolerated|\bno (overall )?[\w ,-]{0,40}(side effects?|risks?|liver injury|injury|toxicity)\b|minimal (effect|impact|risk)|"
         r"\b(over)?hyp(e|ed)\b|very rare|mild[- ]to[- ]moderate|medicines have side effects|whether drug related or not|\bgentle\b|non-?toxic|nothing to worry")
def minimization_lexicon(p): return _trigger(p, MINIM, 'safety-minimizing language')
EFFABS = (r"\bcur(e|es|ed|ing)\b|eliminat\w*|\bheal(s|ing|ed)?\b|100 ?%|one hundred percent|100 percent|complete(ly)? (relief|response|clear)|clear skin|\blasting\b|\blasts\b|"
          r"\bdurable\b|\bfast\b|rapid(ly)?|quick(ly)?|works (with)?in \d+|\d+[-–]\d+ minutes|as soon as|live longer|treat all|doesn'?t come back|\bvaccine\b|guarantee\w*|\bproven\b|99 ?%|\d+(\.\d+)?\s*(x|times) more")
def efficacy_absolutes(p): return _trigger(p, EFFABS, 'absolute/onset/durability efficacy language: verify against PI endpoints')
EXCL = r"\bthe (first and )?only\b|\bfirst and only\b|\bonly (one|FDA|approved|treatment|medicine|drug|therapy|option|oral|topical|non-?\w+)\b|there'?s only one|first[- ]in[- ]class|#1\b|number one|\bleading\b|preferred (choice|treatment)"
def exclusivity_claim(p): return _trigger(p, EXCL, "exclusivity/priority claim: verify")
QOL = r"quality of life|\bQoL\b|living well|live well|feel (better|like (yourself|myself))|get back to|productivity|\benergy\b|daily activities|well-being|wellbeing"
def qol_claim(p): return _trigger(p, QOL, 'QoL/PRO claim: needs prespecified, multiplicity-controlled PRO support')
def nonclinical_data(p):
    t = p.get('text', '')
    ev = [s for s in _spans(r'in vitro|in vivo|preclinical|nonclinical|animal (model|stud)|\bmurine\b|\bmice\b|\brats?\b|cell line', t) if not _has(r'clinical significance (has not been|is unknown|unknown)', s['text'])]
    return _res('fail' if ev else 'pass', ev)
def guideline_citation(p):
    if _meta(p).get('reference_checks'): return _res('pass')
    return _trigger(p, r"\bNCCN\b|\bASCO\b|\bESMO\b|guideline|category [12][AB]?\b|preferred (regimen|recommendation|option)", 'guideline/reference claim: verify version and wording')
CLASSES = r'antipsychotic|opioid|steroid|stimulant|chemo(therapy)?|hormone|benzodiazepine|NSAID|immunosuppressant|insulin|antibiotic'
def not_a_class(p): return _trigger(p, rf"\bnot an? ({CLASSES})|\bunlike other ({CLASSES})|\bnon-?({CLASSES})\b|\bno ({CLASSES})", 'differs-from-class claim: verify against PI 12.1')

# ---------------------------------------------------------------- data presentation
TTE = r"\bPFS\b|\bOS\b|overall survival|progression[- ]free|median (PFS|OS|survival|DOR)|time[- ]to[- ]|event[- ]free|cystectomy[- ]free|disease[- ]specific (overall )?survival|\bDCR\b|disease control|stable disease|\bSD\b|waterfall|tumor (change|shrinkage|volume)|survival"
def single_arm_endpoints(p):
    t = p.get('text', '') + ' ' + (p.get('audio_text') or '')
    sa = (_pi(p).get('trial_design') or '').lower() in ('single-arm', 'single arm', 'uncontrolled') or _has(r'single[- ]arm|open[- ]label,? (single|non-?randomi)|non-?randomi[sz]ed', t)
    if not sa: return _res('not_applicable', detail='trial not single-arm (pi.trial_design)')
    ev = _spans(TTE, t, flags=0 if False else I)
    return _res('fail' if ev else 'pass', ev, 'time-to-event/DCR/SD/waterfall data from a single-arm trial')
POSTHOC = r"post[- ]hoc|exploratory|subgroup|sub-?analys[ie]s|descriptive analysis|separate analysis|pooled analysis|open[- ]label extension|not (pre-?specified|powered|controlled for multiplicity)"
def posthoc_language(p):
    t = p.get('text', '') + ' ' + (p.get('audio_text') or '')
    st = (_meta(p).get('endpoint_status') or '').lower()
    ev = _spans(POSTHOC, t)
    claimy = _has(r'proven|demonstrat|showed|significan|%|\d+(\.\d+)?\s*(x|times)|reduc|improv|relief|as soon as', t)
    if st in ('exploratory', 'post hoc', 'descriptive', 'not multiplicity-controlled') and claimy:
        return _res('fail', ev or _spans(r'as soon as|\d+%|proven|reduc\w*', t, limit=2), f'endpoint status: {st}')
    return _res('fail' if ev and claimy else 'pass', ev, 'exploratory/post hoc analysis presented with efficacy claim')
def pvalue_exploratory(p):
    t = p.get('text', ''); st = (_meta(p).get('endpoint_status') or '').lower()
    pv = _spans(r'\bp\s*[<=≤]\s*0?\.\d+|statistically significant|\bsignificant(ly)?\b', t)
    if not pv: return _res('pass')
    expl = st in ('exploratory', 'post hoc', 'descriptive', 'not multiplicity-controlled') or _has(POSTHOC, t)
    return _res('fail' if expl else 'pass', pv, 'p-value/significance on non-confirmatory endpoint' if expl else '')
REL = r"\d+(\.\d+)?\s*(x|times)\b(?!\s*(daily|a day|per|10\b|10\^))|\d+-\d+x\b|\d+(\.\d+)?%\s*(more|less|lower|greater|higher|fewer|reduction|reduced|decrease|lower risk)"
def relative_without_absolute(p):
    t = p.get('text', '') + ' ' + (p.get('audio_text') or '')
    out = []
    for s in re.split(r'(?<=[.!?”"])\s+|\s\|\s', t):
        if re.search(REL, s, I) and len(re.findall(r'\d+(\.\d+)?\s*%|\b\d+ (in|of|out of) \d+', s, I)) < 2 + (1 if re.search(r'\d+%\s*(more|less|lower)', s, I) else 0):
            out += _spans(REL, s, limit=1)
    return _res('fail' if out else 'pass', out, 'relative measure without absolute figures for both arms')
def control_group_data(p):
    if 'DTC' not in _aud(p): return _res('not_applicable')
    t = p.get('text', '') + ' ' + (p.get('audio_text') or '')
    out = []
    for s in re.split(r'(?<=[.!?”"])\s+|\s\|\s', t):
        if re.search(r'\d+(\.\d+)?\s*%|\b\d+ (in|out of) \d+', s) and not re.search(r'placebo|compared|\bvs\.?|versus|control|without|those taking|sugar pill|than', s, I):
            out += _spans(r'\d+(\.\d+)?\s*%|\b\d+ (in|out of) \d+', s, limit=1)
    return _res('fail' if out else 'pass', out, 'treatment-arm number without control-group number')

# ---------------------------------------------------------------- process / metadata
def form_2253(p):
    m = _meta(p)
    if 'form_2253_id' not in m and 'disseminated' not in m: return _res('needs_input', detail='meta.disseminated / meta.form_2253_id not supplied')
    if m.get('disseminated') and not m.get('form_2253_id'): return _res('fail', detail='disseminated without Form FDA 2253 submission id')
    return _res('pass')
def investigational_disclosure(p):
    t, m = p.get('text', ''), _meta(p)
    inv = m.get('investigational') or _has(r'\b(?!FDA-)[A-Z]{2,5}-\d{3,5}\b', t, 0)
    if not inv: return _res('not_applicable')
    ok = _has(r'investigational', t) and _has(r'not (been )?approved|(safety|efficacy|effectiveness)( and (efficacy|effectiveness|safety))? (have|has) not been established', t)
    bad = _spans(r'\bproven\b|\bsafe\b|\beffective\b|no (\w+ )*side effects?|\bno overall\b', t)
    return _res('fail' if (not ok or bad) else 'pass', bad, 'investigational product lacks status disclosure' if not ok else ('efficacy/safety claim about investigational product' if bad else ''))
def risk_link(p):
    if not re.search(CHAR_LIMITED + '|' + SOCIAL, _pt(p)): return _res('not_applicable')
    t = p.get('text', '') + ' ' + ' '.join(_meta(p).get('links', []))
    ok = _has(r'(https?://|www\.)?[\w.-]+\.\w{2,}/\S*(risk|safety|isi)\S*', t)
    return _res('pass' if ok else 'fail', detail='needs direct link to a risk-only landing page')
def promotional_url(p):
    t = p.get('text', '') + ' ' + ' '.join(_meta(p).get('links', []))
    ev = _spans(r'\b[\w-]*(cure|best|safest|miracle|fastest|guarantee|noside)[\w-]*\.(com|net|org)', t)
    return _res('fail' if ev else 'pass', ev)
def dual_modality(p):
    m = _meta(p); a, s = m.get('major_statement_audio'), m.get('major_statement_supers')
    if not a or s is None: return _res('needs_input', detail='major_statement_audio and major_statement_supers required')
    sup = ' '.join(s) if isinstance(s, list) else s
    na, ns = lambda x: re.sub(r'[^a-z0-9 ]', ' ', x.lower()), None
    keys = [k for k in re.findall(r"[a-z][a-z' -]{3,}", a.lower()) if len(k) > 5]
    missing = [k.strip() for k in re.split(r'[,.;]', a.lower()) if len(k.strip()) > 12 and k.strip() not in na(sup)]
    return _res('fail' if missing else 'pass', detail=f'audio phrases not shown verbatim in SUPERs: {missing[:5]}')
def super_legibility(p):
    f = _meta(p).get('super_format')
    if not f: return _res('needs_input', detail='meta.super_format required')
    bad = f.get('px_height', 0) < 0.035 * f.get('frame_height', 1) or f.get('contrast_ratio', 99) < 4.5
    return _res('fail' if bad else 'pass', detail=str(f))
def super_reading_speed(p):
    s = _meta(p).get('supers')
    if not s: return _res('needs_input', detail='meta.supers [{text,seconds}] required')
    worst = max(len(x['text'].split()) / max(x['seconds'], 0.1) * 60 for x in s)
    return _res('fail' if worst > 238 else 'pass', detail=f'max SUPER reading load {worst:.0f} wpm')
def audio_pacing(p):
    w = _meta(p).get('audio_wpm')
    if not w: return _res('needs_input')
    return _res('fail' if w['major_statement'] > 1.10 * w['benefit'] else 'pass', detail=str(w))
def hcei_disclosures(p):
    if not re.search(r'PAYER|PAYOR|FORMULARY', _aud(p)) or not _meta(p).get('hcei'): return _res('not_applicable')
    t = p.get('text', ''); need = {'limitations': r'limitation', 'data_source': r'data source|source of data|derived from|model inputs', 'generalizability': r'generaliz'}
    if _meta(p).get('differs_from_label'): need['material_differences'] = r'material differences|differs? from the (FDA-approved )?label'
    miss = [k for k, rx in need.items() if not _has(rx, t)]
    return _res('fail' if miss else 'pass', detail=f'missing HCEI disclosures: {miss}')
def unapproved_disclosures(p):
    if not re.search(r'PAYER|PAYOR|FORMULARY', _aud(p)) or not _meta(p).get('unapproved'): return _res('not_applicable')
    t = p.get('text', '')
    ok = _has(r'not (been )?(approved|cleared|licensed)', t) and _has(r'(safety|effectiveness)[\w ,]* (has|have) not been established', t) and _has(r'phase|submitted|stage of development|anticipated', t)
    return _res('pass' if ok and not _has(r'\bproven\b|\bsafe and effective\b', t) else 'fail')
def siuu_disclosures(p):
    if (_meta(p).get('communication_type') or '').upper() != 'SIUU': return _res('not_applicable')
    t = p.get('text', ''); need = {'not_approved': r'not (been )?approved by (the )?FDA', 'not_established': r'(safety|effectiveness)[\w ,]* (has|have) not been established',
        'approved_use': r'(is )?(approved|indicated) for', 'limitations': r'limitation|warning|precaution', 'design': r'study design|limitation|open-label|randomi', 'funding': r'funded by|financial (interest|relationship)|disclos'}
    miss = [k for k, rx in need.items() if not _has(rx, t)]
    return _res('fail' if miss else 'pass', detail=f'missing SIUU disclosures: {miss}')
def misinformation_correction(p):
    if (_meta(p).get('communication_type') or '') != 'misinformation_correction': return _res('not_applicable')
    t = p.get('text', '')
    ok = _has(r'(work|works|working) for|employee of|on behalf of|affiliated with|from the .* team', t) and _has(r'prescribing information|label(ing)?\b|\bPI\b', t)
    promo = _spans(EXCL + '|' + COMPARATIVE + r'|\bbest\b', t)
    return _res('pass' if ok and not promo else 'fail', promo)
def endorser_user(p):
    ev = _spans(r"\bI('ve| have)? (been )?(using|take|use|took|was prescribed)\b|\bmy \w+ (works|worked)\b", p.get('text', ''))
    if not ev: return _res('not_applicable')
    return _res('pass' if _meta(p).get('endorser_verified_user') else 'fail', ev, 'first-person use claim; no bona fide-user verification on file')
def testimonial_typicality(p):
    t = p.get('text', '')
    ev = _spans(r"worked for me|for me,? it works|\bI (lost|cleared|haven'?t had|feel|got)\b|I have cleared|my (skin|pain|migraines?|symptoms) (is|are|was|were) (gone|clear)", t)
    if not ev: return _res('not_applicable')
    ok = _has(r'\d+(\.\d+)?% of (patients|people|participants)|\b\d+ (in|out of) \d+ (patients|people)', t)
    return _res('pass' if ok else 'fail', ev, 'testimonial implies typical results; needs generally-expected-results disclosure')
def material_connection_disclosure(p):
    t = p.get('text', '')
    trig = _meta(p).get('endorser_compensated') or _has(r'partner(ed)? with|teamed up with|ambassador|sponsored', t)
    if not trig: return _res('not_applicable')
    ok = _has(r'#ad\b|#sponsored|paid partnership|paid (spokesperson|by|for)|sponsored by|compensated|in (paid )?partnership with', t)
    return _res('pass' if ok else 'fail', detail='material connection must be disclosed clearly and conspicuously')
def fda_approval_misuse(p):
    t = p.get('text', '')
    ev = _spans(r"FDA[- ]approved[^.]{0,40}\b(safe|safest|best|superior|proven)\b|\b(safe|best|superior)\b[^.]{0,40}FDA[- ]approved|only FDA[- ]approved", t)
    if _meta(p).get('status') and _meta(p)['status'] != 'approved': ev += _spans(r'FDA[- ](approved|cleared)', t)
    return _res('fail' if ev else 'pass', ev)
def rx_indicator(p):
    if 'DTC' not in _aud(p) or not re.search(BROADCAST + r'|print|magazine', _pt(p)): return _res('not_applicable')
    return _res('pass' if _has(r'prescription|\bRx\b|ask your (doctor|health ?care provider) (if|about)', p.get('text', '') + (p.get('audio_text') or '')) else 'fail')
def actor_portrayal(p):
    m, t = _meta(p), p.get('text', '')
    if not (m.get('actor_portrays_hcp') or m.get('real_hcp_compensated')): return _res('not_applicable')
    ok = (not m.get('actor_portrays_hcp') or _has(r'actor', t)) and (not m.get('real_hcp_compensated') or _has(r'paid|compensated', t))
    return _res('pass' if ok else 'fail')
def cost_info(p):
    if 'DTC' not in _aud(p) or not re.search(BROADCAST, _pt(p)): return _res('not_applicable')
    return _res('pass' if _has(r'cost|price|out-of-pocket|savings|afford', p.get('text', '')) else 'fail')
def adult_audience(p):
    pl = _meta(p).get('placement')
    if not pl or not _meta(p).get('age_sensitive'): return _res('not_applicable')
    return _res('fail' if pl.get('adult_pct', 1) < 0.9 else 'pass', detail=str(pl))
def speaker_program_logistics(p):
    g = _meta(p).get('program')
    if not g: return _res('not_applicable')
    bad = []
    if g.get('alcohol'): bad.append('alcohol')
    if g.get('meal_cost_per_head', 0) > g.get('meal_cap', 1e9): bad.append('meal above cap')
    if g.get('venue_type') in ('restaurant', 'bar', 'sports', 'entertainment', 'resort'): bad.append(f"venue {g['venue_type']}")
    if any(a.get('repeat_same_topic') or a.get('relationship') in ('spouse', 'family', 'friend', 'speaker_practice_staff') for a in g.get('attendees', [])): bad.append('attendee without bona fide need/repeat')
    sp = g.get('speaker', {})
    if sp.get('selected_by') in ('sales', 'marketing') or sp.get('roi_used') or sp.get('honorarium', 0) > sp.get('fmv_cap', 1e9): bad.append('speaker selection/compensation')
    if g.get('type') == 'speaker_program' and not _has(r'sponsored by|on behalf of', p.get('text', '')): bad.append('sponsor not identified in materials')
    return _res('fail' if bad else 'pass', detail='; '.join(bad))
def risk_modality_airtime(p):
    tm = _meta(p).get('timing')
    if not tm: return _res('needs_input', detail='meta.timing {benefit_narrated, risk_narrated, benefit_seconds, risk_seconds} required')
    bad = []
    if tm.get('benefit_narrated') and not tm.get('risk_narrated'): bad.append('benefits narrated, risk text-only')
    if tm.get('risk_seconds', 0) < 0.25 * tm.get('benefit_seconds', 0): bad.append('risk airtime < 25% of benefit airtime (Margin heuristic)')
    return _res('fail' if bad else 'pass', detail='; '.join(bad))
def mlr_signoff(p):
    a = _meta(p).get('approvals')
    if a is None: return _res('needs_input')
    roles = {x.get('role', '').lower() for x in a}
    miss = [r for r in ('medical', 'legal', 'regulatory') if r not in roles]
    return _res('fail' if miss else 'pass', detail=f'missing sign-off: {miss}' if miss else '')

def established_name_size(p):
    ns = _meta(p).get('name_sizes')
    if not ns: return _res('needs_input', detail='meta.name_sizes required')
    return _res('fail' if ns.get('established_px', 0) < 0.5 * ns.get('brand_px', 0) else 'pass', detail=str(ns))
def tv_indication_risk(p):
    if not re.search(BROADCAST, _pt(p)) or 'DTC' not in _aud(p): return _res('not_applicable')
    return risk_present(p)

CHECKS = {f.__name__: f for f in [established_name, medwatch_statement, adequate_provision, reminder_ad, risk_present, risk_coverage, risk_after_close,
    indication_qualifiers, comparative_claim, minimization_lexicon, efficacy_absolutes, exclusivity_claim, qol_claim, nonclinical_data, guideline_citation,
    not_a_class, single_arm_endpoints, posthoc_language, pvalue_exploratory, relative_without_absolute, control_group_data, form_2253,
    investigational_disclosure, risk_link, promotional_url, dual_modality, super_legibility, super_reading_speed, audio_pacing, hcei_disclosures,
    unapproved_disclosures, siuu_disclosures, misinformation_correction, endorser_user, testimonial_typicality, material_connection_disclosure,
    fda_approval_misuse, rx_indicator, established_name_size, tv_indication_risk, risk_modality_airtime, actor_portrayal, cost_info, adult_audience, speaker_program_logistics, mlr_signoff]}

def load_rules():
    out = []
    for f in sorted(glob.glob(os.path.join(B, 'rules', '[a-e]_*.json'))):
        out += json.load(open(f))['rules']
    return out

TEXT_CHECKS = {'comparative_claim','minimization_lexicon','efficacy_absolutes','exclusivity_claim','qol_claim','nonclinical_data','guideline_citation',
    'not_a_class','single_arm_endpoints','posthoc_language','pvalue_exploratory','relative_without_absolute','control_group_data','promotional_url',
    'fda_approval_misuse','established_name','risk_present','tv_indication_risk','indication_qualifiers','testimonial_typicality','endorser_user'}
def run_checks(piece, rule_ids=None):
    """Run every implemented deterministic rule (or the given rule_ids) over a piece."""
    res = []
    for r in load_rules():
        if r['check_type'] != 'deterministic' or (rule_ids and r['id'] not in rule_ids): continue
        fn = CHECKS.get(r['detection'].get('check_fn'))
        if not fn: res.append(dict(rule_id=r['id'], check=r['detection'].get('check_fn'), status='not_implemented', evidence=[], detail='')); continue
        if fn.__name__ in TEXT_CHECKS and not (piece.get('text') or piece.get('audio_text') or '').strip():
            out = _res('needs_input', detail='no piece text')
        else: out = fn(piece)
        out.update(rule_id=r['id'], check=fn.__name__); res.append(out)
    return res

if __name__ == '__main__':
    import sys
    piece = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else json.load(sys.stdin)
    for r in run_checks(piece):
        if r['status'] in ('fail', 'pass'): print(f"{r['status'].upper():5} {r['rule_id']:14} {r['check']:28} {r['detail'][:80]} {[e['text'][:60] for e in r['evidence'][:2]]}")
