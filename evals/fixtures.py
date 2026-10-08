"""Builds check-ready `piece` fixtures from OPDP cases and controls, using only what the letter states.
- text: quoted fragments the letter attributes to the piece (fragments the letter quotes as MISSING content are excluded)
- metadata: only facts the letter states (single-arm design, exploratory endpoint, investigational, not submitted on 2253, claimed reminder)
- pi.indication_qualifiers: hand-entered from the letter's own context/rationale (QUALIFIERS below)."""
import re
OMIT_RX = r'(?i)^\s*\[(omission|format|process|ordering)|omit|do(es)? not (communicate|include|specify|disclose|convey|present)|fail(s|ed)? to|not include|lacks?\b|without (any )?(risk|information)'
QUALIFIERS = {
 "UL-20260715-193721-v1": [["lower respiratory tract", "LRTD", "LRTI"]],
 "UL-20260408-191932-v1": [["sALCL", "systemic anaplastic large cell", "CD30-expressing"]],
 "UL-20260206-191036-v2": [["below 50", "<50", "50 x 10"]],
 "UL-20251215-190494-v2": [["ESCC", "esophageal squamous"], ["HER2-negative"], ["PD-L1"]],
 "UL-20250923-189634-v1": [["cardiovascular death", "CV death"], ["hospitalization"]],
 "UL-20250909-188703-v3": [["imatinib"]],
 "UL-20250909-188706-v1": [["topical corticosteroid", "in combination with"]],
 "UL-20250909-188710-v2": [["taxane"]],
 "UL-20220119-155627-v1": [["type 1"]],
 "UL-20220602-158997-v3": [["adjunct to diet", "with diet", "along with diet"]],
 "UL-20211213-155419-v3": [["adults"]],
 "UL-20210308-146528-v3": [["acute"]],
 "UL-20201124-144115-v3": [["pediatric"], ["combination", "multi-phase"]],
 "WL-20200831-sprout-610569-v2": [["not due to", "re:not (due|caused)"]],
 "WL-20200922-nalpropion-v2": [["reduced-calorie diet", "diet"], ["physical activity", "exercise"], ["BMI", "kg/m"]],
 "WL-20250909-lilly-716462-v2": [["tirzepatide-containing", "coadministration"]],
 "WL-20250909-lilly-716475-v2": [["tirzepatide-containing", "coadministration"]],
 "WL-20260313-immunitybio-725468-v5": [["BCG-unresponsive"], ["with BCG", "in combination with BCG"]],
}
def split_quotes(claim):
    have, missing = [], []
    for seg in re.split(r'\s\|\s', claim):
        pre = seg.split('“')[0]
        qs = re.findall(r'“([^”]+)”', seg)
        (missing if re.search(OMIT_RX, pre) else have).extend(qs)
    return have, missing
def brand_generic(product):
    m = re.match(r'^\s*([^(]+?)\s*\(([^)]+)\)', product or '')
    if not m: return (product or '').split('/')[0].strip() or None, None
    return m.group(1).split(' and ')[0].split('/')[0].strip().title(), m.group(2).strip()
def case_fixture(c):
    have, missing = split_quotes(c['claim_text'])
    blob = ' '.join([c['fda_rationale'], c.get('context', ''), c['suggested_check']])
    brand, gen = brand_generic(c['product'])
    pi, meta = {}, {}
    if re.search(r'(?i)single[- ]arm', blob): pi['trial_design'] = 'single-arm'
    if re.search(r'(?i)exploratory|post hoc|not prespecified|not pre-specified|descriptive|multiplicity|not powered|separate analysis', blob): meta['endpoint_status'] = 'exploratory'
    if c['category'].startswith('Promotion of investigational'): meta['investigational'] = True
    if c['category'].startswith('Failure to submit'): meta.update(disseminated=True, form_2253_id=None)
    if c['id'] == 'UL-20211213-155419-v1': meta['claimed_reminder'] = True
    if c['id'] in QUALIFIERS: pi['indication_qualifiers'] = QUALIFIERS[c['id']]
    return dict(text=' | '.join(have), piece_type=c['piece_type'], audience=c['audience'], brand=brand, established_name=gen, pi=pi, meta=meta,
                _missing_quoted=missing)
