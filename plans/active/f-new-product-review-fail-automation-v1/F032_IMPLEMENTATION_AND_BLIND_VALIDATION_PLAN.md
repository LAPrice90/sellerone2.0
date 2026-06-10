# F032 Implementation And Blind Validation Plan

Cycle name:
- `F032 Review Intelligence Cycle`

Purpose:
- Build an AI review layer that checks products before they reach the user.
- Test it with blind examples so the agent cannot simply copy known answers.
- Only accept the cycle when results are consistent, explainable, and useful.

## Plain-English Goal

The user should not be the first person checking whether a product is genuinely good.

F032 should act like a trained reviewer:
- inspect the evidence
- go through a fixed checklist
- separate clear fails from uncertain rows
- pass only genuinely good candidates to the user
- categorise every fail so the system can improve upstream

## Phase 1 - Lock The Evidence Pack

What to build:
- A single evidence pack per SKU/ASIN candidate.
- It must include the information the agent needs without making it search across many files.

Required fields:
- supplier ID
- active run ID
- supplier SKU
- ASIN
- supplier title
- Amazon title
- supplier brand
- Amazon brand
- supplier unit cost
- Amazon price / sell price
- profit per unit
- expected monthly profit
- ROI or profit-on-cost clue
- demand evidence
- seller count / seller ownership evidence
- UK review and variant evidence
- current automated gate result
- current review status

Pass criteria:
- 100% of rows with an ASIN have an Amazon title.
- 100% of rows have supplier SKU.
- 100% of rows have supplier title unless source file genuinely lacks it.
- Missing supplier title rows are listed separately and blocked from clean Pass.
- Evidence pack has a schema check.
- Evidence pack can be rebuilt without changing Google Sheets or the product DB.

## Phase 2 - Build The F032 Decision Output

What to build:
- A durable decision file from the F032 checklist.

Required output:
- `out/analysis_reports/f032_review_intelligence_decisions_latest.csv`

Required decision fields:
- supplier SKU
- ASIN
- supplier title
- Amazon title
- decision bucket
- action
- confidence
- evidence used
- short explanation
- fail category
- rule-tightening candidate
- needs user guidance flag

Allowed actions:
- `remove_from_clean_pass`
- `manual_review`
- `rescan_needed`
- `allow_if_other_checks_pass`

Pass criteria:
- 0 blank decision buckets.
- 0 invalid actions.
- 0 rows promoted directly into final Pass by F032 alone.
- Every fail has a fail category.
- Every manual-review row has a reason.
- Output is stable when rerun on the same input.

## Phase 3 - Implement The Checklist

Checklist items:
- title match
- pack size and quantity
- accessory/refill/filter vs full device
- same brand but different product
- high ROI / suspicious profit
- seller-control risk
- Amazon-only or brand-owner risk
- demand evidence quality
- seller stock and seller count evidence
- UK review count and variant evidence
- missing evidence or rescan needed

Pass criteria:
- Each checklist item has a named decision field.
- Each checklist item has a pass/fail/manual-review explanation.
- Missing evidence is not guessed.
- Suspicious title plus extreme ROI automatically fails.
- Suspicious title without extreme ROI goes to manual review.
- Pack-size ambiguity goes to manual review unless clearly wrong.

## Phase 4 - Blind Agent Test Set

What to build:
- A blind validation file where the agent gets the evidence but not the expected answer.
- A hidden answer file where the expected decision is stored separately.

Files:
- `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_inputs.csv`
- `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_expected.csv`
- `out/analysis_reports/f032_blind_validation_results_latest.csv`

Blind-agent rule:
- The agent may see supplier title, Amazon title, economics, seller evidence, demand evidence, review evidence, and notes that would normally be available before user review.
- The agent must not see user decision, expected action, training label, or hidden answer.

Minimum seed set:
- all current known failed examples
- all current known passed examples
- Fluval high-ROI suspicious match
- Calvin Klein vs Carolina Herrera wrong product
- Joby vs Lexar wrong product
- food/drink pack-size examples after CLF runs
- at least 20 clear passes
- at least 20 clear fails
- at least 20 ambiguous/manual-review rows

Pass criteria:
- 0 known clear fails marked as `allow_if_other_checks_pass`.
- 0 known clear passes marked as `remove_from_clean_pass`.
- At least 95% action agreement on blind examples.
- At least 90% exact bucket agreement on blind examples.
- 100% of high-ROI suspicious-title examples are blocked or manual-reviewed.
- 100% of missing-title or missing-Amazon-title-with-ASIN rows are blocked or manual-reviewed.

## Phase 5 - Consistency Test

What to test:
- Run the blind agent multiple times on the same blind input.
- Compare whether it gives the same action and same bucket.

Required runs:
- 3 blind runs on the same input.

Pass criteria:
- At least 98% same action across the 3 runs.
- At least 95% same decision bucket across the 3 runs.
- 0 cases where a row changes from fail to clear Pass across runs.
- Any inconsistent row is written to a review file with explanation.

## Phase 6 - Rule-Tightening Suggestions

What to build:
- A report that asks, "Could this have been caught earlier?"

Required output:
- `out/analysis_reports/f032_rule_tightening_suggestions_latest.csv`

Required fields:
- fail category
- example SKU/ASIN
- evidence that caught it
- proposed earlier rule
- expected benefit
- false-fail risk
- needs more examples flag

Pass criteria:
- Every repeated fail category has at least one proposed upstream improvement.
- Suggestions are marked as `safe_to_automate`, `needs_more_examples`, or `do_not_automate`.
- No rule suggestion is automatically applied without separate proof.

## Phase 7 - Wire Into User Review

What to build:
- The user review list should only show rows after F032 has made its decision.

Routing:
- clear fail = removed from clean Pass
- manual review = user guidance list
- rescan needed = evidence/rescan queue
- AI clear = final user review candidate

Pass criteria:
- User-facing review list excludes clear F032 fails.
- Manual-review rows are visible with reason.
- F032 removed rows are still auditable.
- No row disappears without a category.

## Phase 8 - Morning Automation

What to build:
- A morning Codex automation that runs F032 and writes the outputs.

Automation should:
- run after the price-list evidence is stable
- avoid overlapping the F owner process
- write outputs only
- summarize counts
- flag only new or worsened issues

Pass criteria:
- Automation runs without overlapping F live writes.
- Automation writes all required F032 outputs.
- Health file has 0 FAIL.
- Known WARNs are tracked, not repeated noisily.
- The final user review list is updated only after all F032 checks complete.

## Phase 9 - Live Proof

What to prove:
- The live system uses F032 correctly.

Pass criteria:
- F-owned proof window completed safely.
- F019 rebuild includes title-match fields.
- F032 outputs are written after F019 review pack build.
- Clear F032 fails do not appear in clean Pass.
- Manual-review rows are still available for user guidance.
- F020, F021, F030, and O review UI tests still pass.

## Definition Of Done

F032 is done only when:
- evidence pack exists and passes schema check
- F032 decisions exist
- blind validation passes
- consistency test passes
- rule-tightening suggestions exist
- user review list receives only F032-filtered rows
- live proof passes
- fail categories feed future improvements

## Current Build Status - 2026-05-20

Phase 1 status:
- code fix applied
- isolated verification passed
- latest evidence pack written
- output: `out/analysis_reports/f032_review_intelligence_evidence_pack_latest.csv`
- evidence rows: `1603`
- supplier SKU missing rows: `0`
- supplier title missing rows: `0`
- Amazon title missing with ASIN rows: `0`

Phase 2 status:
- code fix applied
- isolated verification passed
- latest decision output written
- output: `out/analysis_reports/f032_review_intelligence_decisions_latest.csv`
- decision rows: `1603`
- remove from clean Pass decisions: `1353`
- rescan needed decisions: `246`
- manual review decisions: `1`
- allow if other checks pass decisions: `3`
- health FAIL rows: `0`
- health WARN rows: `0`
- direct final-Pass promotions by F032: `0`

Phase 3 status:
- code fix applied
- isolated verification passed
- full checklist output written
- output: `out/analysis_reports/f032_review_intelligence_checklist_latest.csv`
- checklist rows: `1603`
- blank checklist status rows: `0`
- blank checklist reason rows: `0`
- pack-size calibration added for equivalent wording such as `100 pc` vs `100 pieces`

Phase 4 initial blind split status:
- input-only file created: `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_inputs.csv`
- hidden answer file created: `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_expected.csv`
- blind input rows: `9`
- hidden answer rows: `9`
- leaked answer columns in blind input: `0`
- current seed mix: `5` clear-pass, `3` clear-fail, `1` manual-review/rescan case
- blind input now includes visible supplier-brand guess, Amazon brand, title-rule result, quantity alignment, and pack-size guidance
- minimum seed set ready: `no`

Phase 5 latest blind consistency status:
- three blind reviewer runs completed
- scored output: `out/analysis_reports/f032_blind_validation_results_latest.csv`
- consistency output: `out/analysis_reports/f032_blind_validation_case_consistency_latest.csv`
- acceptable action agreement: `100.0%`
- exact action agreement: `96.3%`
- exact bucket agreement: `96.3%`
- action consistency across 3 runs: `88.89%`
- bucket consistency across 3 runs: `88.89%`
- fail-to-clear flip cases: `0`
- acceptance result: not accepted yet

Phase 6 status:
- code fix applied
- isolated verification passed
- rule-tightening suggestion output written
- output: `out/analysis_reports/f032_rule_tightening_suggestions_latest.csv`
- rule suggestion rows: `10`

Reason not accepted yet:
- the seed set is too small for the planned acceptance threshold
- the remaining blind-agent consistency WARN is the TePe missing-supplier-title row, where one agent chose `rescan_needed` and the others chose `manual_review`
- both TePe outcomes are blocked outcomes, so there were still `0` fail-to-clear flips
- CLF pack-size examples still need to be added when CLF runs

Current next step:
- expand the blind sample set to at least `20` clear-pass, `20` clear-fail, and `20` manual/ambiguous examples
- add CLF food/drink pack-size cases when CLF runs
- then rerun the three-run blind consistency test
