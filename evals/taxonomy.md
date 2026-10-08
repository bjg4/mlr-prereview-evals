# OPDP violation taxonomy (eval set v0)

Source: 279 cases from 111 FDA OPDP letters (103 untitled letters and 8 warning letters), dated 2020-08 to 2026-09. Every case is a positive (`expected_flag: true`).

The **Category** column is a normalized bucket. Each case also keeps `letter_category_label`, which is the finer label and uses the letter's own heading where it has one. The pre-2025 letters use headings such as "False or Misleading Risk Presentation" and "Omission of Material Facts". Most letters from late 2025 onward have no headings, so the label describes the argument FDA makes.

Check-type totals are **149 deterministic and 130 judgment**.
- **Deterministic**: a rule or diff against the PI/MG or the asset's own metadata can catch it. Examples: missing W&P headings, a missing indication qualifier, PFS/OS claims from a single-arm trial, SUPER words-per-minute, no 2253 record.
- **Judgment**: needs an LLM/pairwise judge on the net impression. Examples: imagery vs. effect size, "carefree" lifestyle framing, distracting visuals.

`scripts/build.py` regenerates `taxonomy_table.md` from the case files.

## Counts

| Category | Cases | Letters | Deterministic | Judgment | Primary check type |
|---|---|---|---|---|---|
| Overstatement of efficacy | 41 | 37 | 11 | 30 | judgment |
| Omission of risk information | 38 | 38 | 37 | 1 | deterministic |
| Distracting presentation during risk/major statement (TV) | 37 | 32 | 3 | 34 | judgment |
| Misleading presentation of study data (post hoc / exploratory / single-arm) | 33 | 25 | 20 | 13 | deterministic |
| Minimization of risk | 26 | 19 | 11 | 15 | judgment |
| Broadening of indication / omission of material indication facts | 24 | 24 | 20 | 4 | deterministic |
| Lack of fair balance / risk prominence | 17 | 17 | 17 | 0 | deterministic |
| Unsupported PRO / quality-of-life claims | 15 | 14 | 2 | 13 | judgment |
| Unsubstantiated superiority / comparative claims | 15 | 13 | 2 | 13 | judgment |
| Failure to submit at first use (Form FDA 2253) | 10 | 10 | 10 | 0 | deterministic |
| Major statement not in dual modality (TV) | 8 | 8 | 8 | 0 | deterministic |
| Unsubstantiated efficacy / mechanism claims | 4 | 3 | 1 | 3 | judgment |
| Promotion of investigational / unapproved drug or use | 3 | 2 | 2 | 1 | deterministic |
| Misleading administration / storage / handling presentation | 3 | 3 | 0 | 3 | judgment |
| Misleading claims about safety | 1 | 1 | 1 | 0 | deterministic |
| Misleading representation of drug identity/source | 1 | 1 | 1 | 0 | deterministic |
| Misleading citation of treatment guidelines / references | 1 | 1 | 1 | 0 | deterministic |
| Missing adequate provision / brief summary | 1 | 1 | 1 | 0 | deterministic |
| Failure to use established name / required labeling elements | 1 | 1 | 1 | 0 | deterministic |

Audience split (cases): DTC 203, HCP 66, both 10. Year split (cases): 2020 11, 2021 12, 2022 12, 2023 8, 2024 12, 2025 142, 2026 82.

## Category definitions and how Margin should check them

**Overstatement of efficacy** (41; mostly judgment)
- What it covers: the claims or visuals imply more benefit, faster onset, longer duration or a broader response than the PI supports. Recurring patterns:
  - post-treatment imagery showing near-complete resolution (Austedo, Ingrezza, Qelbree, Velsipity, Jublia)
  - "rapid"/"as soon as" onset claims (Rystiggo, Amvuttra)
  - absolute claims ("Goodbye needles", "zero-migraine days", "cure")
- Deterministic hooks:
  - Compare onset timepoints with the earliest significant timepoint in the PI.
  - Compare responder-rate wording ("many", "get clear skin") with PI rates.
  - Flag "Nx more" ratio framing.
- Judge: pairwise, the asset vs. the same asset with the effect size stated plainly.

**Omission of risk information** (38; deterministic)
- What it covers: product claims with no risk information, or with specific W&Ps, contraindications, boxed-warning elements or MG action statements missing ("stop taking", "get emergency help").
- Where it shows up: booth panels, sponsored links, virtual backgrounds, spokesperson and executive interviews, podcasts.
- Check: diff the risk content against every PI Boxed Warning sub-element, contraindication, W&P heading and MG "most important"/"possible side effects" item. A PI URL, "See ISI" or sitelink labels never count as mitigation.

**Distracting presentation during risk/major statement (TV)** (37; judgment)
- What it covers: scene changes, choreography, music, gags, animals, zooms or narrative reveals during the major statement. It also covers efficacy-qualifying SUPERs that run too fast to read or compete with the voiceover (Fabhalta 433 wpm, Kisqali 400 wpm), and indication or limitations-of-use content buried under visuals (Jardiance).
- Checks:
  - Deterministic sub-check: SUPER words-per-minute, flagged above ~238 wpm.
  - Storyboard judge: count cuts in the major-statement window and rate visual salience.

**Misleading presentation of study data** (33; mostly deterministic)
- Single-arm oncology trials:
  - DCR or stable disease (Fyarro, Lytgobi, Pemazyre, Tazverik, Imdelltra)
  - PFS/OS, cystectomy-free or DSS endpoints (Anktiva, Iclusig, Krazati, Fyarro)
- Post hoc or exploratory endpoints: Auvelity anhedonia subscale, Ingrezza Week 2, Nemluvio 48 h, Kisqali extended OS.
- Descriptive p-values: Nextstellis.
- Enriched rollover populations: Ingrezza satisfaction.
- Check: map each claim to its endpoint and check whether it was primary, key secondary with alpha, or post hoc. Also check whether the trial design was single-arm. Disclaimers do not cure.

**Minimization of risk** (26)
- What it covers: framings that downplay risks.
  - Lexicon examples: "overhyped", "a lot of hype", "mild to moderate", "whether drug related or not".
  - Organ "low impact" claims that contradict a contraindication.
  - Lifestyle framing that ignores monitoring (Calquence).
  - Risk ordered with ARs before W&Ps (Danziten).
  - Undercutting a safer-sex behavior (Apretude).
- Check: a lexicon plus PI-cross-reference covers the deterministic half. The judge handles the impression.

**Broadening of indication / omission of material indication facts** (24; deterministic)
- What it covers: missing qualifiers such as:
  - combination partner (Nemluvio, Anktiva)
  - line of therapy or prior-therapy specifics (Danziten imatinib, Pluvicto taxane-delay)
  - population or biomarker (Tevimbra "upper GI cancers")
  - composite endpoint components (Farxiga)
  - limitations of use (Zepbound, Addyi)
  - adjunct to diet and exercise
- Check: diff the stated indication against every clause in PI §1.

**Lack of fair balance / risk prominence** (17; deterministic)
- What it covers:
  - SUPER font size, contrast or placement
  - risk after the signature block or after fade-to-black
  - risk airtime ratio (Oprah special: 4 of 42 minutes)

**Unsupported PRO / quality-of-life claims** (15; judgment)
- What it covers:
  - emotional or social transformation narratives ("I'm back", memes with "likes")
  - QoL claims from PROs without alpha (Fruzaqla)
  - item-level claims when only a total score was studied (Fasenra AQLQ)
  - "carefree" framing in progressive disease where KCCQ/6MWT still declined (Attruby, Amvuttra)

**Unsubstantiated superiority / comparative claims** (15; judgment)
- What it covers:
  - head-to-head superiority claims from open-label trials with differential dropout (Skyrizi)
  - manufacturing or formulation advantages (Jeuveau)
  - "unique profile" safety claims (Nextstellis)
  - real-world-evidence adherence comparisons (Hemady)
  - "only/first" claims

**Failure to submit at first use (Form FDA 2253)** (10; deterministic, process): check that a 2253 record exists for every disseminated asset, including executive interviews, podcasts and paid search.

**Major statement not in dual modality (TV)** (8; deterministic): align the audio transcript with the SUPER text and flag text-only or audio-only risk items.

**Smaller buckets** (1–4 cases each):
- mechanism-of-action overclaims (Contrave "2 ways", Camzyos "targets the cause")
- unapproved use or route (Anktiva "all cancers", subcutaneous)
- administration-time claims (Kesimpta "1 minute", Opdivo Qvantig "3 minutes")
- outdated guideline citation (Iclusig NCCN)
- missing established name (Adzenys sponsored links)
- missing adequate provision
- drug identity/source

## Deterministic vs judgment split

| Check type | Cases | Share |
|---|---|---|
| deterministic | 149 | 53% |
| judgment | 130 | 47% |

Judgment cases are concentrated in DTC TV:
- DTC: 104 judgment / 99 deterministic
- HCP: 24 judgment / 42 deterministic

The deterministic categories need three structured inputs: the product's PI (Indications, BW, CI, W&P, Clinical Studies endpoint table), the MG, and asset metadata (transcript, SUPER timings, 2253 ID).
