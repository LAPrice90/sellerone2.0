# Response

## Ticket
- `f-history-risk-overrides-pass-v1`
- Goal: move Issue 2 from planning to proven upstream routing using the same pattern already used for demand-range routing.

## Implemented Scope
- Added read-only history-risk audit:
  - `scripts/one_off/F025_build_history_risk_pass_conflict_audit.py`
  - `tests/test_f025_build_history_risk_pass_conflict_audit.py`
- Added history-risk evidence fields and rule ingestion to fail triage:
  - `scripts/one_off/F021_build_new_product_review_fail_triage.py`
  - `tests/test_f021_build_new_product_review_fail_triage.py`
- Added upstream history-risk routing to pass-pack builder:
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
  - `tests/test_f019_build_live_price_file_near_miss_pack.py`

## Command Proof
- `python -m py_compile scripts/one_off/F025_build_history_risk_pass_conflict_audit.py tests/test_f025_build_history_risk_pass_conflict_audit.py scripts/one_off/F021_build_new_product_review_fail_triage.py tests/test_f021_build_new_product_review_fail_triage.py scripts/one_off/F019_build_live_price_file_near_miss_pack.py tests/test_f019_build_live_price_file_near_miss_pack.py`
  - Result: pass
- `pytest tests/test_f025_build_history_risk_pass_conflict_audit.py tests/test_f021_build_new_product_review_fail_triage.py tests/test_f019_build_live_price_file_near_miss_pack.py -q`
  - Result: `32 passed`
- `python scripts/one_off/F025_build_history_risk_pass_conflict_audit.py --pass-path out/analysis_reports/f_live_price_file_pass_review_20260423T133613Z.csv`
  - Result: audit rebuilt from the pre-upstream-routing pass snapshot (`226` rows) and written to latest audit path
- `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
  - Result: upstream routing rebuilt pass and near-miss outputs
- `python scripts/one_off/F021_build_new_product_review_fail_triage.py`
  - Result: triage rebuilt with history and demand evidence columns

## History Audit Result
- Output: `out/analysis_reports/f_history_risk_pass_conflict_audit_latest.csv`
- Input pass rows audited: `226`
- `history_risk_code` counts:
  - `history_fail_phase_avoid`: `109`
  - `backtest_avoid_commercial_avoid_or_exit`: `16`
  - `exit_only_clean_pass`: `22`
  - `history_risk_clear`: `79`
- Primary action counts:
  - `remove_from_clean_pass`: `147`
  - `allow_if_other_checks_pass`: `79`
- Unclassified rows: `0`

## Upstream Routing Proof (F019)
- Clean Pass count before rebuild: `226`
- Clean Pass count after rebuild: `79`
- Rows removed from clean Pass by history rule (audit remove action): `147`
- Rows routed to manual review by history rule: `0`
- Demand-range routing still active:
  - `demand_routed_remove_from_clean_pass_rows`: `10`
  - `demand_routed_manual_review_rows`: `2`

## Triage Proof (F021)
- Output: `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- Final `fail_type` counts:
  - `type_1_data_or_calc`: `1119`
  - `type_2_known_policy_or_memory`: `1`
  - `type_3_missing_evidence_rescan_needed`: `2153`
- Unclassified rows: `0`
- `B0C8C3JF9X` final row:
  - `review_pack_type=near_misses`
  - `fail_type=type_2_known_policy_or_memory`
  - `fail_reason_code=review_memory_fail_decision`
  - `evidence_source=feeder_review_events:o-ui-f-review-bfc06f252e51`
  - `demand_conflict_code=amazon_blank_bbp_high`
  - `history_risk_code=history_fail_phase_avoid`

## Scope Guard Confirmation
- No queue changes made.
- No Google Sheets write made.
- No local DB alignment changes made.
- No scraper run made.
- No A script run.
- No full F061 rescan run.
- No `WORK_LOG.md` update made.
