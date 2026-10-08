# Scoreboard: round1-evaldata-E3-near-miss-2

Generated 2026-10-08T07:22:37-07:00. Judge model `anthropic/claude-haiku-5.5`. Phase spend so far $0.3341. Items {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 37, 'near_miss/holdout': 14}.

| Metric | dev | holdout |
|---|---|---|
| Judge single-item sensitivity (violating → fail) | 0.932 | 0.932 |
| Judge single-item specificity (compliant → pass) | 0.735 | 0.767 |
| Judge balanced accuracy (primary) | 0.833 | 0.850 |
|   near-miss balanced accuracy | 0.932 | 0.964 |
|   easy balanced accuracy | 0.800 | 0.814 |
| Pairwise accuracy (both orders) | 0.997 | 0.983 |
|   pairwise near-miss accuracy | 1.000 | 1.000 |
| Position: acc when correct=A | 0.993 | 0.983 |
| Position: acc when correct=B | 1.000 | 0.983 |
| Position: order flips (pairs) | 1 | 2 |
| Det claim-level recall (letter cases) | 0.823 | 0.923 |
| Det targeted FP rate (controls) | 0.196 | 0.238 |
| Det any claim-level fire on controls | 0.256 | 0.235 |
| Unparseable judge answers | 0 | 1 |

By rule family (dev, single-item balanced accuracy / n_pos / n_neg): A: 0.821 (81/81); B: 0.8266 (49/49); C: 0.75 (4/4); D: 0.9 (5/5); E: 1.0 (8/8)
By check_type (dev): deterministic: 0.8667; judgment: 0.8104
Coverage: 78/81 rules have ≥1 positive and ≥1 negative case; missing: B-SM-03, D-SP-04, E-DTC-13.

