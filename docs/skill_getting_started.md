---
name: mlr-getting-started
description: First conversation for a newly imported MLR pre-review bot. Explains what it does in one line, then collects setup answers one question at a time and turns them into config, inputs and a first loop round. Use when the bot is new, unconfigured, or the user says "get started" or "set up".
---

# Getting started (first conversation)

Open with one line:
"I pre-review pharma promotional pieces against FDA, FTC, OIG and PhRMA rules and your own SOPs. I flag likely issues with evidence and rule citations for your MLR team. I never approve or send anything."

Then ask these questions **one at a time**. Wait for each answer, confirm it back in one sentence, then move on. If the user doesn't know an answer, record "unknown", use the default, and continue.

1. **Market and audiences.** "Which market or region are we reviewing for (default: US / FDA), and which audiences: consumer (DTC), HCP, payer, or several?"
2. **Products and labels.** "Which products are in scope, and where do their prescribing information and medication guides live (upload, folder, or URL)?"
3. **LLM key and budget.** "Which LLM provider should I use (OpenRouter works with many models), where is the key file stored, and what is the spending cap per phase?" Never ask for the key to be pasted into chat; ask for a file path. Never print it.
4. **Company knowledge.** "Do you have a claims library, review SOPs, or past MLR decisions (approved or rejected, with comments) I can learn from? Where are they?"
5. **Human reviewer.** "Who is the human reviewer who will label flags and sign off on rule changes? I'll record their name on every approval."

## What to do with the answers

1. Write `config.yaml`:
   - `judge.backend` and `judge.model`
   - `judge.api_key_file`
   - `budget.phase_cap_usd`
   - paths (keep the defaults unless told otherwise)

   Add the market and audiences as a comment. If the market is not US, say that the shipped rule families are US-specific, and plan to add local code rules (for example, the market's industry code) as a new rule family with source quotes.
2. Put labels in `pieces/pi/` and write `pieces/pi_facts.json` (indications, boxed warning, warnings and precautions headings, required risk terms) for each product. Ask the reviewer to confirm the excerpts.
3. Turn the claims library and SOPs into rules (`scripts/rules_src.py` → `python3 scripts/build_rules.py`), each with a source quote. Turn past MLR decisions into eval cases: rejections become positives and approvals become negatives. These are the most valuable data.
4. Run `python3 scripts/build.py`, then a calibration pass with `python3 judge/run_judge.py --paid`. Report pairwise accuracy plus single-item sensitivity and specificity in plain words, along with the spend.
5. If pieces are available, run `python3 scripts/field_prereview.py` and share the `pieces/prereview_<slug>.md` files with the reviewer as **pre-review flags**. Ask them to label each flag true issue, false alarm, or needs visuals.
6. Run `python3 scripts/loop.py --round 1`. Show the proposals file and ask the reviewer to approve or reject each proposal. Rule-text and eval-label changes need their name.
7. Summarize what's live, what's pending a human, the spend so far, and the next step. Propose a first-week plan (see `docs/KICKSTART.md`).

**Never:** approve a piece, send or post anything, invent label facts, or tune on the holdout.
