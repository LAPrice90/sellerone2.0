# Profit Calculation Correction Response

Status: implemented with isolated proof, local rebuild artifacts, and partial live scraper proof
Response timestamp UTC: `2026-04-23T15:14:00Z`

## Root Cause
- Confirmed.
- Profit was inflated because stored and downstream values were derived from:
  - `profit_per_unit = sale_price - break_even`
- `break_even` is a threshold sell price, not true unit cost.

## Implementation Summary
- Added shared fee-based profit helper:
  - `scripts/flows/F/_profit_model.py`
- Updated upstream Webscrape profit logic to use fee-based net profit:
  - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- Passed fee context into Webscrape from F061 owner flow:
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- Updated F071 qualification profit to use fee-based net profit (not break-even subtraction):
  - `scripts/flows/F/F071_build_backtest_input_view.py`
- Added read-only audit script:
  - `scripts/one_off/F027_build_profit_formula_conflict_audit.py`
- Added/updated tests:
  - `tests/test_f027_build_profit_formula_conflict_audit.py`
  - `tests/test_f019_build_live_price_file_near_miss_pack.py`
- Updated F019 to attach corrected profit evidence and surface corrected values in review rows when audit evidence exists:
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`

## Commands Run
- `python -m py_compile ...` (requested set): pass
- `pytest tests/test_f027_build_profit_formula_conflict_audit.py tests/test_f019_build_live_price_file_near_miss_pack.py tests/test_f021_build_new_product_review_fail_triage.py -q`: pass (`33 passed`)
- `python scripts/one_off/F027_build_profit_formula_conflict_audit.py`: pass
- safe local rebuilds executed:
  - `python scripts/flows/F/F071_build_backtest_input_view.py` (via `PYTHONPATH=.` due local import resolution)
  - `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
  - `python scripts/one_off/F021_build_new_product_review_fail_triage.py`

## Audit Output
- Path: `out/analysis_reports/f_profit_formula_conflict_audit_latest.csv`
- Rows: `3322`
- Counts by `profit_formula_code`:
  - `profit_inflated_break_even_subtraction=238`
  - `profit_formula_review_needed=30`
  - `profit_missing_inputs_rescan_needed=3054`
- Counts by `recommended_action`:
  - `remove_from_clean_pass=238`
  - `manual_review=30`
  - `targeted_rescan_needed=3054`
- Unclassified rows: `0`

## B0B7298QN6 Before and After
- Identity:
  - `candidate_id=70215661ab3af8a951a00b3c517bb404f4d6648b`
  - `supplier_sku=1204860`
- Before:
  - old per-unit profit shown: `6.92`
  - stored expected 30d profit field: `210.6`
  - implied by `40 * 6.92`: `276.80`
- After (review pack with audit-corrected evidence applied):
  - corrected per-unit profit shown: `4.38431`
  - corrected expected 30d profit shown: `175.372381`
  - delta per unit: `2.53569`
  - delta total (vs stored expected field): `35.227619`
- Final review-pack location:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- Final classification/action:
  - `profit_formula_code=profit_inflated_break_even_subtraction`
  - `profit_recommended_action=remove_from_clean_pass`
  - `profit_evidence_source` points to audit-backed evidence linkage.

## F019 Clean Pass Before and After Rebuild
- Before rebuild (previous run output): `pass_review_rows=47`, `near_miss_review_rows=3275`
- After rebuild: `pass_review_rows=47`, `near_miss_review_rows=3276`

## F021 Fail Type Counts (after rebuild)
- `type_1_data_or_calc=1122`
- `type_2_known_policy_or_memory=1`
- `type_3_missing_evidence_rescan_needed=2153`
- `unclassified_rows=0`

## Partial Live Scraper Proof
- Weekend F061 stocklist scan started after the profit code change.
- New scrape-evidence rows checked after `2026-04-23T15:17:26Z`: `30`.
- Rows with enough price/profit fields checked: `30`.
- Rows still matching old formula `avg_30_day_price - break_even`: `0`.
- Current proof status:
  - live scraper path is writing corrected profit values for newly scanned rows
  - full all-row refresh remains incomplete until the weekend scan finishes

## Guardrails
- No Google Sheets writes: confirmed
- No local DB alignment changes: confirmed
- No scraper run inside the profit implementation ticket: confirmed
- Separate weekend F061 scanner is now running as the live refresh/proof window
- No A script run: confirmed
- Full F061 refresh: in progress through the weekend stocklist scanner
- No WORK_LOG update: confirmed
