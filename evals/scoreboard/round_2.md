# Scoreboard: round2-C2r-pair-category-match-recheck

Generated 2026-10-08T07:51:52-07:00. Judge model `anthropic/claude-haiku-5.5`. Phase spend so far $1.2515. Items {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 37, 'near_miss/holdout': 14}.

| Metric | dev | holdout |
|---|---|---|
| Judge single-item sensitivity (violating → fail) | 0.966 | 0.966 |
| Judge single-item specificity (compliant → pass) | 0.728 | 0.700 |
| Judge balanced accuracy (primary) | 0.847 | 0.833 |
|   near-miss balanced accuracy | 0.946 | 0.964 |
|   easy balanced accuracy | 0.814 | 0.793 |
| Pairwise accuracy (both orders) | 1.000 | 0.983 |
|   pairwise near-miss accuracy | 1.000 | 1.000 |
| Position: acc when correct=A | 1.000 | 0.983 |
| Position: acc when correct=B | 1.000 | 0.983 |
| Position: order flips (pairs) | 0 | 2 |
| Det claim-level recall (letter cases) | 0.823 | 0.923 |
| Det targeted FP rate (controls) | 0.196 | 0.238 |
| Det any claim-level fire on controls | 0.256 | 0.235 |
| Unparseable judge answers | 0 | 1 |

By rule family (dev, single-item balanced accuracy / n_pos / n_neg): A: 0.8167 (90/90); B: 0.875 (44/44); C: 1.0 (2/2); D: 0.9 (5/5); E: 1.0 (6/6)
By check_type (dev): deterministic: 0.9405; judgment: 0.8095
Coverage: 78/81 rules have ≥1 positive and ≥1 negative case; missing: B-SM-03, D-SP-04, E-DTC-13.

