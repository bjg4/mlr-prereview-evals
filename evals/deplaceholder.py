"""Eval-data fix: remove placeholder leakage from SYNTHETIC compliant rewrites.
v1 rewrites contain bracketed placeholders ('[ORR from PI]') and presentation notes that make the compliant side trivially
recognizable. This asks the judge-family LLM to rewrite each one in the ORIGINAL's format, with no brackets other than the
'[Visual]' convention the letter excerpts themselves use, and no invented numbers. Every new number must appear in the
case material; otherwise the rewrite is rejected and the v1 text is kept. Output cached in evals/controls_rewrites_v2.jsonl."""
import os, sys, json, re, concurrent.futures as cf
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0] = [f'{B}/scripts', f'{B}/judge']
from common import CFG, load_jsonl, path
import llm
OUT = f'{B}/evals/controls_rewrites_v2.jsonl'
SYS = """You edit SYNTHETIC eval data for a pharma promotional-review tool. You get an FDA-cited ORIGINAL excerpt and a draft COMPLIANT REWRITE that fixes the cited problem but contains bracketed placeholders/notes.
Rewrite the compliant version so it reads like a real excerpt of the same piece:
- Keep the fix of the cited problem fully intact. Keep the same drug, audience, and general message.
- Use the ORIGINAL's formatting conventions (VO:/SUPER:/quotes/' | ' separators). If the original describes visuals as '[Visual] ...', describe compliant visuals the same way; no other square brackets anywhere.
- Do NOT invent numbers, percentages, study names, dates or label wording. Use only numbers that appear in the provided material; otherwise use qualitative wording (e.g., 'more people taking X had ... than with placebo').
- Risk content: state risks only if named in the provided material; otherwise use a general but real-sounding statement such as 'X can cause serious side effects, including ...' only with risks named in the material, or 'See Important Safety Information below.' when no risks are named.
Return JSON: {"rewrite_text": str, "notes": str}"""
def nums(t): return set(re.findall(r'\d+(?:\.\d+)?', t))
def main():
    cases = {c['id']: c for c in load_jsonl(path('cases'))}; ctrls = load_jsonl(path('controls'))
    done = {r['control_id'] for r in load_jsonl(OUT) if r.get('reject_reason') != 'empty'}  # empty = truncated output; retried with more tokens
    llm.load_openrouter_key(); model = CFG['judge']['model']; cost = [0.0]
    def leaky(t): return bool(re.search(r'\[(?!Visual\])', t))
    todo = [k for k in ctrls if k['id'] not in done and leaky(k.get('compliant_rewrite_v1', k['compliant_rewrite']))]
    def one(k):
        c = cases[k['source_case_id']]; v1 = k.get('compliant_rewrite_v1', k['compliant_rewrite'])
        msg = (f"Drug: {k['product']} | Piece: {k['piece_type']} | Audience: {k['audience']}\nFDA rationale: {c['fda_rationale']}\nContext: {c.get('context','')}\n\n"
               f"ORIGINAL (cited):\n{k['original_claim']}\n\nDRAFT COMPLIANT REWRITE:\n{v1}")
        r = llm.chat_full([{'role': 'system', 'content': SYS}, {'role': 'user', 'content': msg}], model, CFG['judge']['backend'], temperature=0, max_tokens=4000, json_mode=True)
        cost[0] += float((r.get('usage') or {}).get('cost') or 0)
        txt = r['choices'][0]['message']['content']; m = re.search(r'\{.*\}', txt, re.S)
        o = json.loads(m.group(0)) if m else {}
        new = (o.get('rewrite_text') or '').strip()
        allowed = nums(k['original_claim'] + ' ' + c['fda_rationale'] + ' ' + c.get('context', '') + ' ' + v1 + ' ' + k['product'])
        bad_nums = sorted(nums(new) - allowed)
        ok = bool(new) and not leaky(new) and not bad_nums
        return dict(control_id=k['id'], model=model, rewrite_text=new, notes=o.get('notes'), accepted=ok,
                    reject_reason=None if ok else ('empty' if not new else ('brackets remain' if leaky(new) else f'unverified numbers {bad_nums}')))
    with cf.ThreadPoolExecutor(8) as ex, open(OUT, 'a') as f:
        for fut in cf.as_completed([ex.submit(one, k) for k in todo]):
            try: f.write(json.dumps(fut.result(), ensure_ascii=False) + '\n')
            except Exception as e: print('error', str(e)[:150])
    rows = list({r['control_id']: r for r in load_jsonl(OUT)}.values())  # last row per control wins
    print(f'deplaceholder: {len(todo)} processed this run, cost ${cost[0]:.4f}; total rows {len(rows)}, accepted {sum(r["accepted"] for r in rows)}')
    return cost[0]
if __name__ == '__main__':
    c = main()
    sys.path.insert(0, f'{B}/scripts'); from engine import add_spend
    if c: add_spend(c, 'deplaceholder rewrites')
