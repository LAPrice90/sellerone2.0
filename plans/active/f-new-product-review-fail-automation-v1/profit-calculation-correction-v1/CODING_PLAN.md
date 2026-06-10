# Coding Plan

## Ticket
- Name: `f-profit-calculation-correction-v1`
- Scope: remove break-even subtraction inflation from New Product Review profit fields
- Owner flow: F

## Current Phase
- Phase 3 complete: root-cause implementation, isolated tests, audit run, and safe local rebuild artifacts generated

## Root Cause
- Current flow stores `profit_per_unit_30d` as `sale_price - break_even`.
- `break_even` is a threshold sell price, not product cost.
- This overstates real profit and inflates downstream review-pack decisions.

## Planned Fix Strategy
- Add a shared fee-based net-profit helper in flow F.
- Recompute per-unit profit in Webscrape from cost and fee inputs.
- Recompute F071 qualified monthly profit from fee-based per-unit profit.
- Add a read-only audit script to compare old stored values against corrected values.
- Keep one-off scripts out of daily loops.

## Allowed Files
- `scripts/flows/F/_profit_model.py` (new shared helper)
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/one_off/F027_build_profit_formula_conflict_audit.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py` (compatibility fields only if needed)
- `scripts/one_off/F021_build_new_product_review_fail_triage.py` (compatibility only if needed)
- `tests/test_f027_build_profit_formula_conflict_audit.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `tests/test_f021_build_new_product_review_fail_triage.py`
- `plans/active/f-new-product-review-fail-automation-v1/FIX_LIST.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN_STATUS.md`
- `plans/active/f-new-product-review-fail-automation-v1/profit-calculation-correction-v1/*`

## Audit Output
- `out/analysis_reports/f_profit_formula_conflict_audit_latest.csv`

Required audit columns:
- `candidate_id`
- `supplier_sku`
- `asin`
- `title`
- `review_pack_type`
- `price_basis`
- `units_basis`
- `old_profit_per_unit_gbp`
- `corrected_profit_per_unit_gbp`
- `old_expected_profit_next_30d_gbp`
- `corrected_expected_profit_next_30d_gbp`
- `profit_delta_per_unit_gbp`
- `profit_delta_total_gbp`
- `cost`
- `fba_fee`
- `referral_fee`
- `digital_fee`
- `est_shipping`
- `vat`
- `api_live_price`
- `bbp_live_sell_price`
- `bbp_30d_avg_price`
- `break_even`
- `profit_formula_code`
- `recommended_action`
- `evidence_source`

## Rule Codes
- `profit_inflated_break_even_subtraction`
- `profit_clear`
- `profit_missing_inputs_rescan_needed`
- `profit_formula_review_needed`

## Tests and Proof Commands
```powershell
python -m py_compile scripts/one_off/F027_build_profit_formula_conflict_audit.py scripts/flows/F/F071_build_backtest_input_view.py scripts/flows/F/legacy_scanner_2_1/Webscrape.py scripts/one_off/F019_build_live_price_file_near_miss_pack.py scripts/one_off/F021_build_new_product_review_fail_triage.py tests/test_f027_build_profit_formula_conflict_audit.py
pytest tests/test_f027_build_profit_formula_conflict_audit.py tests/test_f019_build_live_price_file_near_miss_pack.py tests/test_f021_build_new_product_review_fail_triage.py -q
python scripts/one_off/F027_build_profit_formula_conflict_audit.py
```

## Safe Local Rebuild Candidates
- `python scripts/flows/F/F071_build_backtest_input_view.py`
- `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `python scripts/one_off/F021_build_new_product_review_fail_triage.py`

Run each only after side-effect checks confirm local-file output only.

## Live Monitoring Target
- None for this ticket; proof is artifact-based one-shot rebuild and audit output.

## Poll Cadence
- Not applicable; single-run proof path.

## Success Threshold
- No `sell_price - break_even` usage for per-unit profit in Webscrape output.
- F071 qualification profit no longer derived from break-even subtraction.
- Audit has required columns with zero unclassified rows.
- B0B7298QN6 corrected profit is materially lower than old value.

## Timeout Rule
- If required fee inputs are missing for a row, classify as `profit_missing_inputs_rescan_needed` and do not invent values.

## Automatic Next Step
- After isolated tests pass and audit output is generated, run safe local rebuild scripts and write proof summary into `RESPONSE.md`.
