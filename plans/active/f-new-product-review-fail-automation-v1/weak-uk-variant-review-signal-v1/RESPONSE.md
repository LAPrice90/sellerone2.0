# Response

## Ticket
- Ticket: `f-weak-uk-variant-review-signal-v1`
- Date: 2026-04-23
- Status: implementation and proof complete for current stored-evidence routing

## Files Changed
- `scripts/one_off/F026_build_uk_review_signal_audit.py` (new)
- `tests/test_f026_build_uk_review_signal_audit.py` (new)
- `scripts/one_off/F021_build_new_product_review_fail_triage.py`
- `tests/test_f021_build_new_product_review_fail_triage.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `plans/active/f-new-product-review-fail-automation-v1/weak-uk-variant-review-signal-v1/RESPONSE.md`

## Commands Run
- `python -m py_compile scripts/one_off/F026_build_uk_review_signal_audit.py tests/test_f026_build_uk_review_signal_audit.py scripts/one_off/F021_build_new_product_review_fail_triage.py tests/test_f021_build_new_product_review_fail_triage.py scripts/one_off/F019_build_live_price_file_near_miss_pack.py tests/test_f019_build_live_price_file_near_miss_pack.py`
  - Result: pass
- `pytest tests/test_f026_build_uk_review_signal_audit.py tests/test_f021_build_new_product_review_fail_triage.py tests/test_f019_build_live_price_file_near_miss_pack.py -q`
  - Result: `44 passed`
- `python scripts/one_off/F026_build_uk_review_signal_audit.py`
  - Result: pass
- `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
  - Result: pass
- `python scripts/one_off/F021_build_new_product_review_fail_triage.py`
  - Result: pass

## Audit Output
- Path: `out/analysis_reports/f_uk_review_signal_audit_latest.csv`
- Total rows: `3322`
- Counts by `uk_review_code`:
  - `uk_reviews_lt3`: `693`
  - `uk_reviews_3_to_5`: `165`
  - `uk_reviews_6_to_9`: `102`
  - `uk_reviews_10_plus`: `342`
  - `uk_reviews_missing`: `2020`
- Unclassified rows: `0`

## F019 Upstream Routing Proof
- Clean Pass count before rebuild: `79`
- Clean Pass count after rebuild: `47`
- Rows removed from clean Pass by UK review rule: `22` (`uk_review_routed_remove_from_clean_pass_rows`)
- Rows routed to manual review by UK review rule: `10` (`uk_review_routed_manual_review_rows`)
- UK review targeted rescan routed from pass lane in this run: `0` (`uk_review_routed_targeted_rescan_needed_rows`)
- Post-rebuild clean Pass UK buckets:
  - `uk_reviews_lt3`: `0`
  - `uk_reviews_3_to_5`: `0`
  - `uk_reviews_6_to_9`: `7`
  - `uk_reviews_10_plus`: `40`
  - `uk_reviews_missing`: `0`

## Routing Regression Proof
- Demand-range routing still active:
  - `demand_routed_remove_from_clean_pass_rows=10`
  - `demand_routed_manual_review_rows=2`
- History-risk routing still active:
  - `history_routed_remove_from_clean_pass_rows=175`
  - `history_routed_manual_review_rows=0`
- Source: `out/analysis_reports/f_live_price_file_review_summary_latest.csv`

## F021 Triage Proof
- Output path: `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- Final counts by `fail_type`:
  - `type_1_data_or_calc`: `1121`
  - `type_2_known_policy_or_memory`: `1`
  - `type_3_missing_evidence_rescan_needed`: `2153`
- Unclassified rows: `0`

## B0C8C3JF9X Final Classification
- Found in final triage output.
- Final row:
  - `fail_type=type_2_known_policy_or_memory`
  - `fail_reason_code=review_memory_fail_decision`
  - `evidence_source=feeder_review_events:o-ui-f-review-bfc06f252e51`
  - `demand_conflict_code=amazon_blank_bbp_high`
  - `history_risk_code=history_fail_phase_avoid`
  - `uk_review_code=uk_reviews_3_to_5`
- Classification remains correct with memory fail as primary.

## Scope Guard Confirmation
- No queue change made.
- No Google Sheets write made.
- No local DB alignment change made.
- No scraper run made.
- No A script run made.
- No full F061 rescan run made.
- No WORK_LOG.md update made.
