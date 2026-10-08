# Margin single-item judge prompt (template)

Used by `judge/run_judge.py --mode single`. Absolute pass/fail on one rule for one piece. Anchors come from the rule's
detection spec. Run on originals (expected FAIL) and synthetic compliant rewrites (expected PASS).

---
SYSTEM:
(same system message as pairwise_prompt.md)

USER:
Product: {{product}}
Piece type: {{piece_type}} | Audience: {{audience}}
Label facts (authoritative): {{label_facts}}

Rule {{rule_id}} ({{rule_source}}):
{{rule_text}}

Question: {{rule_question}}
PASS anchor: {{pass_anchor}}
FAIL anchor: {{fail_anchor}}

Piece:
<<<
{{text}}
>>>

Respond with JSON only:
{"verdict": "pass" | "fail", "confidence": 0.0-1.0, "missing_context": true|false,
 "evidence": "<exact span from the piece that decided it, or 'absent: ...'>", "reason": "<=2 sentences"}
Set missing_context=true if you could not decide reliably without information not provided (e.g., full PI, visuals).
