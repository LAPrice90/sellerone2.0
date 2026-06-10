# Execution Batch 001

## Purpose
- Lock the fail taxonomy baseline and produce the first deterministic Type 1 fail triage output from current live artifacts.

## Scope guardrails
- Only do:
  - classify rows using existing data sources only
  - produce read-only analysis outputs
- Do not change:
  - supplier queue files
  - scraper owner scripts
- Do not add:
  - new runtime loops
  - ad-hoc direct scraper entrypoints

## Files allowed to change
- `scripts/one_off/F020_build_new_product_review_fail_triage_pack.py`
- `tests/test_f020_build_new_product_review_fail_triage_pack.py`
- `plans/active/f-new-product-review-fail-automation-v1/*`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN.md`
- supporting files:
  - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
  - `out/systems/F/live/f_screening_row_state_live.csv`
  - `out/systems/F/live/feeder_legacy_first_checks_live.csv`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`

## Tasks
### Task 1
- Goal:
  - build a baseline fail taxonomy map from current fail codes and near-miss types
- Files:
  - `scripts/one_off/F020_build_new_product_review_fail_triage_pack.py`
- Notes:
  - each row must map to one and only one fail type

### Task 2
- Goal:
  - add deterministic Type 1 rule checks for data or calculation issues
- Files:
  - `scripts/one_off/F020_build_new_product_review_fail_triage_pack.py`
  - `tests/test_f020_build_new_product_review_fail_triage_pack.py`
- Notes:
  - no rescan logic in this batch

## Tests
- Command:
  - `python -m py_compile scripts/one_off/F020_build_new_product_review_fail_triage_pack.py tests/test_f020_build_new_product_review_fail_triage_pack.py`
  - `pytest tests/test_f020_build_new_product_review_fail_triage_pack.py -q`
- Expected result:
  - tests pass and output schema is stable

## Monitoring plan
- Live proof needed:
  - no
- Forced proof window:
  - not required
- Artifacts to poll:
  - `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- Poll cadence:
  - one check after script run
- Success threshold:
  - output exists with non-empty row set and explicit fail type per row
- Timeout rule:
  - park with exact source mismatch or schema error
- Fallback if forced proof is blocked:
  - not applicable
- Next phase after success:
  - Batch 002 (Type 2 auto-fail)
- Notification mode:
  - milestone only
- User interruption threshold:
  - interrupt only if source evidence contradicts fail taxonomy mapping

## Proof required
- Row counts:
  - output row count by fail type
- Health rows:
  - unclassified row count
- Output files:
  - `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
  - `out/analysis_reports/f_new_product_review_fail_triage_summary_latest.csv`
- Notes:
  - include source timestamp and active run id in output metadata

## Completion checklist
- [ ] Scope held
- [ ] Files changed only in allowed set
- [ ] Tests passed
- [ ] Proof captured
- [ ] Reply file updated
