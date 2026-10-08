# Margin eval set v0: FDA OPDP enforcement letters (positives)

This is the first eval set for Margin's MLR pre-review. Every case is a real claim, presentation or omission that FDA's Office of Prescription Drug Promotion (OPDP) cited as false or misleading. Each case records:
- the letter's own wording
- FDA's reasoning
- the regulation cited
- whether a deterministic check could catch it, or whether it needs a judgment/pairwise judge (following Crosby's evals approach)

## What's in it

| | |
|---|---|
| Cases | **279** (`opdp_cases.jsonl`), all `expected_flag: true` |
| Letters processed | **111** in total: 103 untitled letters and 8 warning letters |
| Letters skipped | 2 (see below) |
| Date range | Aug 2020 to Sep 2026 |
| Check types | 149 deterministic, 130 judgment |
| Audience | DTC 203, HCP 66, both 10 |

Cases by letter year:

| Year | Cases | Processed letters |
|---|---|---|
| 2020 | 11 | 4 |
| 2021 | 12 | 4 |
| 2022 | 12 | 3 |
| 2023 | 8 | 4 |
| 2024 | 12 | 5 |
| 2025 | 142 | 66 |
| 2026 | 82 | 25 |

Piece types (processed letters):
- TV/broadcast: 57
- web pages: 16
- videos/podcasts/interviews: 14
- exhibit booths: 4
- print/newsletter: 4
- social: 3
- email: 3
- paid search: 3
- other: 7

See `taxonomy.md` for categories, counts and how to check each one.

## Files

```
mlr/
  evals/
    opdp_cases.jsonl     # the eval cases (one JSON object per line)
    taxonomy.md          # categories, definitions, det/judgment split
    taxonomy_table.md    # auto-generated counts table
    README.md            # this file
  letters/
    manifest.csv/.json   # one row per letter: date, company, product, letter type, URL,
                         #   promo-material URLs, piece type, audience (DTC/HCP), regs cited, status
    text/<media_id>.txt  # archived letter text (108 files; WL-<slug>.txt for warning letters)
    pdf/<media_id>.pdf   # raw PDFs where recoverable (46)
    text_status.csv      # per-letter archived-text quality: full / partial / missing / unusable_raw_pdf
  scripts/
    index_rows.tsv       # untitled-letter index (date, company, product, media id, promo media ids)
    wl_rows.tsv          # warning letters included
    cases/<letter_id>.json  # hand-extracted cases per letter (source of truth)
    build.py             # cases/*.json -> jsonl + manifest + taxonomy_table.md, then runs verify.py
    verify.py            # checks every quoted fragment in claim_text against archived letter text
    mk.py, split_exa.py, body*.py  # helpers
```

To regenerate everything, run `python3 scripts/build.py`.

## Schema (`opdp_cases.jsonl`)

| field | meaning |
|---|---|
| `id` | `<source_letter>-v<n>` |
| `source_letter` | `UL-YYYYMMDD-<fda media id>` or `WL-YYYYMMDD-<slug>` |
| `letter_type` | Untitled Letter / Warning Letter |
| `letter_date`, `company`, `product` | from the FDA index / letter |
| `piece_type` | the promotional piece as the letter describes it (e.g., "DTC TV ad (US-99628)") |
| `audience` | `DTC`, `HCP`, or `DTC+HCP` |
| `category` | normalized bucket (see taxonomy.md) |
| `letter_category_label` | finer label; uses the letter's own heading when it has one |
| `letter_heading` | the letter's section heading, when present (older letters) |
| `claim_text` | **verbatim** quotes from the letter, in curly quotes, joined by ` \| ` when one violation cites several claims. Non-verbal violations are described in brackets: `[Omission] …`, `[Visual] …`, `[Format] …`, `[Process] …` |
| `context` | surrounding facts FDA relies on (PI numbers, disclaimers present, visuals) |
| `expected_flag` | always `true` in v0 |
| `fda_rationale` | FDA's reasoning, condensed |
| `regulation` | the citation FDA gives for that violation. Letters from late 2025 onward cite no CFR section in the body, so these are recorded as `FD&C Act (false or misleading)` |
| `check_type` | `deterministic` (rule/diff vs PI, MG or asset metadata) or `judgment` (needs an LLM/pairwise judge) |
| `suggested_check` | how Margin could catch it |
| `quote_check` | result of automated verification: `verified`, `no_quoted_text` (omission/visual/format cases), `not_found_in_partial_text`, or `not_checked` (archived text unavailable) |
| `source_url` | canonical fda.gov URL |

Grain: there is one case per distinct violation argument in a letter. If FDA makes one argument about five claims, that is one case with five quotes. If FDA makes separate risk-omission and distraction arguments about the same TV ad, that is two cases.

## Sources and method

- **Canonical sources** are fda.gov:
  - the CDER OPDP untitled-letters index (`/media/<id>/download` PDFs)
  - individual warning-letter pages
- **How the text was read:** the box cannot reach fda.gov directly (Akamai 401). Letter text was therefore read through WebFetch and an Exa web-fetch API (`web_fetch_exa`).
  - When Exa returned raw PDF bytes, they were decoded locally and run through `pdftotext`.
  - Archived copies are in `letters/text` and `letters/pdf`.
- **Quote verification:** `verify.py` checks each quoted fragment against the archived letter text, after normalization (whitespace, quote style, footnote markers).
  - 186 cases verified, with no mismatches.
  - 79 have no quotable text by nature (omissions, visuals, format).
  - 14 could not be checked automatically because the archived copy is partial or unreadable. These were taken from a full-text read of the letter during extraction.
  - Two claims were corrected during verification:
    - A Duobrii testimonial had an extra sentence that was not in the letter; it was removed.
    - FDA's bracketed expansions were restored in the Kisqali and Brukinsa quotes.
- **Scope rule:** only enforcement against approved-product manufacturers is included. Compounder, telehealth and unapproved-drug-seller warning letters are excluded (e.g., the ~58 compounded GLP-1/ED letters of 9 Sep 2025, and Hims & Hers).

## Gaps and known problems

1. **Positives only.** There are no negative controls yet. A model that flags everything scores 100%. Precision is unmeasured until compliant counterparts exist.
2. **No pairwise pairs yet.** The 130 judgment cases need matched "fixed" versions to rank against. Examples: the same TV storyboard without cuts during the major statement, or the same claim with the effect size stated.
3. **Warning-letter coverage is incomplete.** The FDA warning-letter index is JS-rendered, so WLs were found by search. Included:
   - 2020: Sprout/Addyi, Nalpropion/Contrave
   - 2025: Lilly Zepbound ×2, Lilly Oprah special, Novo Oprah special, Aytu/Adzenys
   - 2026: ImmunityBio/Anktiva

   Known missing, by industry counts:
   - 2 more 2020 WLs
   - 2 in 2021, including CytoDyn/leronlimab (URL not found)
   - 1 in 2022
   - 1 in 2023
   - about 4 more 2025 manufacturer WLs
   - any 2026 WLs after March
4. **Skipped letters (2):**
   - Nexlizet (Esperion, 2025-12-19, media 190458)
   - PharmaTher ketamine (2025-09-30, media 189734)

   In both cases the fetch tools returned the PDF truncated at their 1M-character cap, so the PDF was unreadable. These need a manual download.
5. **Partial letters:**
   - Bimzelx "Can't Wait To Say 'I'm Back'" (188695): the extracted text is missing the middle page(s). Only the first violation is recorded.
   - Fabhalta: the ≥ symbols are dropped in the SUPER quote.
   - The Wegovy letter text had OCR artifacts.
6. **CBER letters are excluded.** OPDP is CDER; CBER/APLB letters (e.g., FluMist 2025-09-09, Kymriah 2026-03-09) are not in this set.
7. **Promo materials were not reviewed.** Cases quote what the letter says, not the underlying ads. The ad PDFs and MP4s FDA attaches (`promo_material_urls` in the manifest) were not opened. This means `[Visual]` cases have no storyboard frames yet.
8. **Skew.** 224 of the 279 cases (80%) are from 2025–26. Most are DTC TV, driven by the Sept 2025 crackdown. HCP and digital/social cases are thinner, and 2021–2024 OPDP output was very low (about 4–6 letters a year).
9. **Category mapping is judgment.** Buckets are normalized from heterogeneous letter language, and late-2025+ letters have no headings. `letter_category_label` preserves the finer label.
10. **No PI snapshots.** Deterministic checks need the PI/MG version in force on the letter date. These have not been collected.

## Next steps

1. **Negative controls.** For each case, write or collect a compliant counterpart. Options:
   - FDA-cleared versions of the same campaign
   - the corrective ads companies ran
   - rewrites that fix only the cited issue

   Also sample unflagged, 2253-submitted materials for the same products.
2. **Pairwise pairs.** For the 130 judgment cases, build (violative, fixed) pairs and score the judge on preference accuracy.
3. **Deterministic harness.** Pull PI/MG text per product and letter date. Implement the top rules:
   - risk diff vs BW/CI/W&P/MG
   - indication-qualifier diff
   - single-arm endpoint guard
   - post hoc endpoint guard
   - SUPER wpm
   - 2253 presence
4. **Fill the WL gaps** above, process the 2 skipped letters, and fill the Bimzelx partial.
5. **Attach the promo PDFs/MP4s** so visual and format cases can be evaluated on the actual asset rather than FDA's description.
6. **Refresh monthly.** OPDP has been posting letters at a much higher rate since Sept 2025. Re-run the index scrape and append.

## Phase 2 (rulebook + Crosby-style evals), added 2026-10-07
- `../method.md`: what Crosby's eval method says (source: crosby.ai/blog/how-we-do-evals-at-crosby) and how Margin applies it.
- `../rules/`: 81 rules in 5 source-family JSON files + `index.json`; source texts are archived in `../rules/sources/`. Source of truth: `../scripts/rules_src.py` → `../scripts/build_rules.py`.
- `../checks/`: deterministic checks (`python3 -m checks.margin_checks piece.json`).
- `fixtures.py` + `run_deterministic.py` → `det_results.json` (recall on OPDP deterministic cases, false positives on controls). `det_results_v0_pretuning.json` is a frozen snapshot from before lexicon tuning.
- `controls.jsonl` (SYNTHETIC compliant rewrites; built by `make_controls.py` from `controls_raw.jsonl` [LLM cache] + `controls_manual.py` [agent-authored]).
- `pairwise.jsonl` (SYNTHETIC; built by `make_pairwise.py` from controls + `near_miss_src.py`).
- `../judge/`: prompt templates + `run_judge.py` (OpenRouter; key read at runtime from ~/.config/openrouter/api_key; responses cached in `judge/results/cache.jsonl`; $3 cap). Results: `judge/results/status.json`, `raw.jsonl`; v1 snapshot `status_v1.json`/`raw_v1.jsonl`; hand review of failures `judge/failure_review.json`.
- `report.md`: coverage, recall, FP, pairwise, judge status, gaps.
Rebuild everything: `python3 scripts/build.py` (set `MARGIN_RUN_JUDGE=1` to also run the judge).
