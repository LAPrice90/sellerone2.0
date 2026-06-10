# F032 Fail Reason Checklist Execution And Test Plan

Date: 2026-05-20

## Plain English Aim

The New Product Review Fail Reason Checklist must become part of the Codex AI decision process, not a separate note.

In simple terms:

- the scanner finds possible products
- FPM155 builds the AI review queue
- Codex reviews each queued product against the fail-reason checklist
- Codex writes a decision file
- FPM155 unlocks only the products with completed Codex decisions
- the UI never sees products that skipped the checklist

## Checklist Source

Checklist file:

- `plans/active/f-new-product-review-fail-automation-v1/FAIL_REASON_REVIEW_CHECKLIST.md`

Automation guide:

- `plans/active/f-new-product-review-fail-automation-v1/F032_CODEX_AI_REVIEW_AUTOMATION.md`

Daily automation:

- name: `F032 Codex AI review gate`
- id: `f032-codex-ai-review-gate`
- run time: `07:30` UK time

## Execution Phases

### Phase 1 - Make Checklist Mandatory

Goal:

- Codex must use the fail-reason checklist before writing a decision.

Execution:

- Update the automation guide so it names the checklist file.
- Update the daily automation prompt so it loads the checklist.
- Require every `codex_ai_reason` to mention the strongest checklist reason.

Pass criteria:

- automation guide names `FAIL_REASON_REVIEW_CHECKLIST.md`
- automation prompt names `FAIL_REASON_REVIEW_CHECKLIST.md`
- decision buckets map to checklist categories

### Phase 2 - Add Checklist Categories To AI Queue Review

Goal:

- every queued product can be judged against the same seven fail reasons.

Checklist categories:

- wrong product match
- seller-controlled or risky seller situation
- profit looks better than it really is
- demand evidence is too weak
- UK review or variant risk
- feedback too vague to learn from
- empty or missing evidence

Execution:

- For each `ai_review_queue.csv` row, Codex reads the title, brand, pack/quantity, ROI/profit, seller, demand, review, and evidence fields.
- Codex selects one final action.
- Codex writes the strongest category into `codex_ai_decision_bucket` and explains it in `codex_ai_reason`.

Pass criteria:

- every decision has a valid action
- every decision has a non-blank reason
- every non-clear decision has a fail category or manual/rescan category
- low confidence rows are not allowed to clean Pass

### Phase 3 - Controlled Sample Test

Goal:

- prove Codex can apply the checklist before the live flow depends on it.

Test setup:

- create a small isolated handoff with sample rows covering:
  - clear product match
  - wrong product match
  - same brand but accessory/device mismatch
  - pack-size mismatch
  - high ROI plus suspicious title
  - seller-control risk
  - weak demand or missing evidence
  - UK review/variant risk

Execution:

- run `python scripts\one_off\F035_refresh_f032_ai_review_queues.py --root <test root>`
- confirm `ai_review_queue.csv` is created
- have Codex write `codex_ai_review_decisions.csv`
- rerun `python scripts\one_off\F035_refresh_f032_ai_review_queues.py --root <test root>`

Pass criteria:

- FPM155 publishes `manifest.csv` only after Codex decisions exist
- `manifest.csv` has `ai_gate_status=passed`
- `manifest.csv` has `operator_ready_flag=1`
- clear row appears in `ai_operator_pass_review.csv`
- manual row appears in `ai_operator_near_miss_review.csv` or `ai_manual_review.csv`
- rescan row appears in `ai_rescan_queue.csv`
- clear fail row appears in `ai_removed_from_clean_pass_audit.csv`
- no row is visible without `f032_decision_id`
- no row is visible without `codex_ai_action`

### Phase 4 - Blind Consistency Test

Goal:

- prove the Codex decision process is consistent enough to trust.

Execution:

- use the existing blind validation pattern
- run three independent Codex decision passes over the same hidden-answer sample
- compare action and category consistency

Pass criteria:

- zero fail-to-clear flips
- no high-risk row becomes clean Pass
- action consistency target: at least `95%`
- bucket consistency target: at least `90%`
- every disagreement is recorded with the reason

### Phase 5 - Live F-Flow Proof

Goal:

- prove the real scanner handoff activates the queue and blocks the UI until Codex has decided.

Safe proof rule:

- do this only at an F-owned safe boundary, not over the top of an active scanner write.

Execution:

- let or run a controlled supplier scan to completion
- confirm FPM150 writes `candidate_manifest.csv`
- confirm FPM155 writes `ai_review_queue.csv`
- confirm O400 shows no raw rows while `codex_ai_review_decisions.csv` is incomplete
- let the Codex automation write decisions
- rerun or wait for F035/FPM155 finalization
- confirm O400 shows only AI-gated rows
- confirm F090 intake reads only AI-gated Pass rows

Pass criteria:

- `live_cycle_events.csv` contains `ai_review_gate`
- `ai_review_queue.csv` exists
- `codex_ai_review_decisions.csv` covers every queued `f032_decision_id`
- `manifest.csv` has `ai_gate_status=passed`
- `manifest.csv` has `operator_ready_flag=1`
- O400 visible rows all have `f032_decision_id`
- O400 visible rows all have `codex_ai_action`
- F090 intake rows all trace to F032/Codex decisions

### Phase 6 - Learning Review

Goal:

- decide later which work can be taken off Codex safely.

Execution:

- compare Codex decisions against user final decisions
- group differences by fail-reason checklist category
- identify repeated safe patterns that can become earlier automatic rules

Pass criteria:

- false-clear candidates are recorded
- false-block candidates are recorded
- manual-review training cases are recorded
- rule-tightening suggestions name the source checklist category

## Definition Of Done

This checklist integration is done only when:

- the automation uses the fail-reason checklist
- Codex writes a decision for every queued row
- FPM155 refuses to publish rows without Codex decisions
- O400 cannot show rows that skipped the checklist
- F090 cannot ingest rows that skipped the checklist
- controlled sample proof passes
- live F-flow proof passes

## Current New Product Review Proof - 2026-05-20 - Superseded Wrong-Scope Test

Scope:

- isolated proof copy of the current New Product Review clean Pass rows
- live review files were not changed
- Google Sheets and local DB were not changed
- user later clarified these were manually passed rows, not the intended unassessed review rows

Proof root:

- `out/proof/f032_current_new_product_review_manual_review_test_20260520T135941Z`

Rows tested:

- source clean Pass rows: `3`
- SKUs: `1144846`, `1257989`, `1174830`
- ASINs: `B082NMTZC2`, `B09FQCWKPW`, `B084CTW7T8`

Proof sequence:

- copied the current New Product Review clean Pass rows into an isolated FPM155 handoff
- ran F035/FPM155 once to create `ai_review_queue.csv`
- wrote Codex checklist decisions as `manual_review`
- ran F035/FPM155 again to publish the AI-gated manifest
- loaded the isolated result through O400 review UI loader

Result:

- queue rows: `3`
- Codex decision rows written: `3`
- manifest `ai_gate_status`: `passed`
- manifest `operator_ready_flag`: `1`
- operator clean Pass rows: `0`
- operator near-miss rows: `3`
- manual review rows: `3`
- UI pass rows: `0`
- UI manual review rows: `3`

Conclusion:

- this proof only proves the mechanics on manually passed rows
- it is not the acceptance proof for unassessed New Product Review rows
- the correct unassessed-row proof is recorded below

## Correct Unassessed New Product Review Proof - Kuriboh - 2026-05-20

Scope:

- isolated proof copy of the unassessed Bliss row named by the user
- live review files were not changed
- Google Sheets and local DB were not changed

Proof root:

- `out/proof/f032_unassessed_new_product_review_kuriboh_test_20260520T142028Z`

Row tested:

- supplier: `bliss_distribution`
- source run: `fpm_bliss_distribution_20260518T094415Z`
- supplier SKU: `KONKKS`
- ASIN: `B09HKZWBDN`
- supplier title: `Yu-Gi-Oh! - Kuriboh Kollection Sleeves 50 Pack`
- Amazon title: `Yu-Gi-Oh! Kuriboh Kollection Card Sleeves`
- supplier cost: `1.89`
- profit per unit: `1.24`
- approximate profit-on-cost: `65.61%`

Proof sequence:

- copied the unassessed Kuriboh raw Pass row into an isolated FPM155 handoff
- seeded the supplier title from the Bliss source price file
- ran F035/FPM155 once to create `ai_review_queue.csv`
- confirmed FPM155 blocked the operator manifest while the Codex decision was missing
- wrote the Codex decision as `manual_review`
- reran F035/FPM155 to publish the AI-gated manifest
- loaded the isolated result through O400 review UI loader

Result before Codex decision:

- candidate manifests found: `1`
- queued rows: `1`
- pending Codex decision rows: `1`
- manifest path: blank
- operator ready flag: `0`

Codex decision:

- action: `manual_review`
- category: `pack_size_or_quantity`
- reason: supplier title says `Sleeves 50 Pack`, but Amazon title says `Card Sleeves` without confirming the 50 pack wording
- ROI note: `65.61%` profit-on-cost, not extreme enough to fail by itself

Result after Codex decision:

- manifest `ai_gate_status`: `passed`
- manifest `operator_ready_flag`: `1`
- operator clean Pass rows: `0`
- operator near-miss rows: `1`
- manual review rows: `1`
- removed rows: `0`
- rescan rows: `0`
- O400 clean Pass visible rows: `0`
- O400 manual review visible rows: `1`

Conclusion:

- the Kuriboh unassessed row is not shown as clean Pass after the AI gate
- it is routed to Manual Review because the supplier pack quantity is not proven by the Amazon title
- this is the correct acceptance proof for the user-specified example

## AI Check Notes And Amazon Page Evidence Addendum - 2026-05-20

Reason:

- the user should not have to re-work the same uncertainty from scratch
- the UI should show the short AI note telling the user exactly what to check
- the AI gate should use Amazon page evidence beyond the title when the scraper captures it

What changed:

- O400 now turns Codex/F032 manual-review decisions into a short `AI check note`
- example for Kuriboh: `AI check: confirm the Amazon listing is for 50 units per pack.`
- F061 scrape evidence can now carry:
  - `product_detail_text`
  - `product_description`
  - `product_feature_bullets`
- product description is captured from the Amazon page after the BBP/pre-review kill gate has passed
- first-choice Amazon description XPath: `//*[@id="productDescription"]/p[1]/span`
- F019 review packs can now carry those fields forward as:
  - `amazon_product_detail_text`
  - `amazon_product_description`
  - `amazon_feature_bullets`
- F032/FPM155 AI queues can now include those Amazon page evidence fields for Codex review
- FPM155 health now includes `ai_queue_amazon_page_text_columns_present`

Proof:

- focused compile passed for the changed scraper, schema, F019, F032/FPM155, and O400 files
- focused tests passed: `3 passed`
- exact XPath selector proof passed: `2 passed`
- broader affected tests passed:
  - `19 passed, 55 deselected`
  - `50 passed`
- isolated Kuriboh UI loader proof now shows:
  - helper label: `AI check note`
  - helper text: `AI check: confirm the Amazon listing is for 50 units per pack.`
- controlled F061 proof scrape:
  - Kuriboh proof root: `out/proof/f061_amazon_description_xpath_20260520T144431Z`
  - Kuriboh result: stopped before browser scrape with `OVER50K`, so no Amazon description scrape was attempted
  - successful proof root: `out/proof/f061_amazon_description_xpath_datacollection_20260520T144608Z`
  - successful proof row: DHB `PDL504` / `B001AI8AKI`
  - BBP/pre-review gate: passed
  - scrape evidence runtime: `ok`
  - `scrape_attempted=True`
  - `scrape_success=True`
  - `product_description=TePe Interdental Blue Brushes 0.6mm - Pack of 6`
  - `product_feature_bullets` populated
  - chart daily rows: `366`

Live limitation:

- existing live rows do not already contain Amazon description or bullet text
- those fields will populate only after the affected products are rescanned through F061

Next live proof:

- trigger: next safe F-owned F061 scrape that writes `feeder_legacy_scrape_evidence_live.csv`
- artifact to inspect: `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- success condition: new successful scrape rows contain `product_description` or `product_feature_bullets` when Amazon exposes those page sections
- remediation if missing: inspect the page selectors and add another Amazon description/bullet fallback selector
