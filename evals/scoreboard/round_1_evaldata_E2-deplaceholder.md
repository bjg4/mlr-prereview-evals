# Scoreboard: round1-evaldata-E2-deplaceholder

Generated 2026-10-08T07:21:25-07:00. Judge model `anthropic/claude-haiku-5.5`. Phase spend so far $0.3090. Items {'easy/dev': 110, 'easy/holdout': 46, 'near_miss/dev': 21, 'near_miss/holdout': 6}.

| Metric | dev | holdout |
|---|---|---|
| Judge single-item sensitivity (violating → fail) | 0.924 | 0.922 |
| Judge single-item specificity (compliant → pass) | 0.702 | 0.750 |
| Judge balanced accuracy (primary) | 0.813 | 0.836 |
|   near-miss balanced accuracy | 0.881 | 1.000 |
|   easy balanced accuracy | 0.800 | 0.814 |
| Pairwise accuracy (both orders) | 0.996 | 0.981 |
|   pairwise near-miss accuracy | 1.000 | 1.000 |
| Position: acc when correct=A | 0.992 | 0.981 |
| Position: acc when correct=B | 1.000 | 0.981 |
| Position: order flips (pairs) | 1 | 2 |
| Det claim-level recall (letter cases) | 0.823 | 0.923 |
| Det targeted FP rate (controls) | 0.196 | 0.238 |
| Det any claim-level fire on controls | 0.256 | 0.235 |
| Unparseable judge answers | 0 | 1 |

By rule family (dev, single-item balanced accuracy / n_pos / n_neg): A: 0.821 (81/81); B: 0.7926 (41/41); C: 0.75 (4/4); D: 0.75 (2/2); E: 1.0 (3/3)
By check_type (dev): deterministic: 0.8298; judgment: 0.8036
Coverage: 56/81 rules have ≥1 positive and ≥1 negative case; missing: A-502A-01, B-CCN-02, B-CFL-02, B-MI-01, B-PAY-02, B-PN-02, B-SIUU-01, B-SIUU-02, B-SM-02, B-SM-03, B-SM-04, D-CIA-01, D-CIA-02, D-SP-02, D-SP-04, D-SP-05, E-CODE-02, E-CODE-07, E-DTC-04, E-DTC-09, E-DTC-10, E-DTC-11, E-DTC-13, E-DTC-16, E-DTC-19.

