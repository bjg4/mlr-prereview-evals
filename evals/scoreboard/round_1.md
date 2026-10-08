# Scoreboard: round1-C1-reminder-boxed-warning

Generated 2026-10-08T07:29:52-07:00. Judge model `anthropic/claude-haiku-5.5`. Phase spend so far $0.5197. Items {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 37, 'near_miss/holdout': 14}.

| Metric | dev | holdout |
|---|---|---|
| Judge single-item sensitivity (violating → fail) | 0.946 | 0.932 |
| Judge single-item specificity (compliant → pass) | 0.708 | 0.750 |
| Judge balanced accuracy (primary) | 0.827 | 0.841 |
|   near-miss balanced accuracy | 0.946 | 0.964 |
|   easy balanced accuracy | 0.786 | 0.803 |
| Pairwise accuracy (both orders) | 1.000 | 0.992 |
|   pairwise near-miss accuracy | 1.000 | 1.000 |
| Position: acc when correct=A | 1.000 | 1.000 |
| Position: acc when correct=B | 1.000 | 0.983 |
| Position: order flips (pairs) | 0 | 1 |
| Det claim-level recall (letter cases) | 0.823 | 0.923 |
| Det targeted FP rate (controls) | 0.196 | 0.238 |
| Det any claim-level fire on controls | 0.256 | 0.235 |
| Unparseable judge answers | 0 | 1 |

By rule family (dev, single-item balanced accuracy / n_pos / n_neg): A: 0.8149 (81/81); B: 0.8163 (49/49); C: 0.75 (4/4); D: 0.9 (5/5); E: 1.0 (8/8)
By check_type (dev): deterministic: 0.8583; judgment: 0.8046
Coverage: 78/81 rules have ≥1 positive and ≥1 negative case; missing: B-SM-03, D-SP-04, E-DTC-13.

